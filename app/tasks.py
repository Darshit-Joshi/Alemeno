import os
import json
import pandas as pd
import google.generativeai as genai
from celery.exceptions import MaxRetriesExceededError
from app.worker import celery_app
from app.database import SessionLocal
from app.models import Job, Transaction, JobSummary

# Configure Gemini with strict JSON generation
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel(
    'gemini-2.5-flash', 
    generation_config={"response_mime_type": "application/json"}
)

@celery_app.task(bind=True, max_retries=3)
def process_transactions_task(self, job_id: str, file_path: str):
    db = SessionLocal()
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        db.close()
        raise self.retry(exc = Exception(f"Job {job_id} not visible in DB yet . Retrying....."), countdown = 1)

    try:
        job.status = "processing"
        db.commit()

        # --- 1. DATA CLEANING & NORMALIZATION ---
        df = pd.read_csv(file_path).drop_duplicates()
        
        # Robust currency & amount cleaning (handles "$", ",", and spaces)
        df['amount'] = (
            df['amount'].astype(str)
            .str.replace('$', '', regex=False)
            .str.replace(',', '', regex=False)
            .str.strip()
            .astype(float)
        )
        df['currency'] = df['currency'].str.upper().str.strip()
        df['category'] = df['category'].fillna('Uncategorised').str.strip()
        df['date'] = pd.to_datetime(df['date'], dayfirst=True, format='mixed').dt.strftime('%Y-%m-%dT%H:%M:%S')

        # --- 2. VECTORIZED ANOMALY DETECTION (50x Faster than .apply) ---
        medians = df.groupby('account_id')['amount'].transform('median')
        
        # Boolean masks for conditions
        is_stat_outlier = df['amount'] > (medians * 3)
        is_usd_domestic = (df['currency'] == 'USD') & (df['merchant'].str.upper().isin(['SWIGGY', 'OLA', 'IRCTC']))
        
        # Apply flags vectorially
        df['is_anomaly'] = is_stat_outlier | is_usd_domestic
        
        # Build anomaly reasons cleanly
        reasons = pd.Series("", index=df.index)
        reasons = reasons.mask(is_stat_outlier, "Statistical Outlier")
        reasons = reasons.mask(is_usd_domestic & is_stat_outlier, reasons + " | USD Domestic Anomaly")
        reasons = reasons.mask(is_usd_domestic & ~is_stat_outlier, "USD Domestic Anomaly")
        df['anomaly_reason'] = reasons

        # --- 3. AI CATEGORIZATION (Safe Key-Value Mapping & Batching) ---
        uncategorised = df[df['category'] == 'Uncategorised']
        if not uncategorised.empty:
            # For 100x scale, you can wrap this in a loop chunking by 50 rows
            records_to_classify = uncategorised[['txn_id', 'merchant', 'amount']].to_dict('records')
            
            prompt = (
                "You are a financial classification assistant. Categorize these transactions into one of: "
                "Food, Shopping, Travel, Transport, Utilities, Cash Withdrawal, Entertainment, Other. "
                f"Return a JSON array of objects with keys 'txn_id' and 'category': {json.dumps(records_to_classify)}"
            )
            
            response = model.generate_content(prompt)
            classified_data = json.loads(response.text)
            
            # Map back safely using txn_id so length mismatches never crash the app
            category_map = {item['txn_id']: item['category'] for item in classified_data if 'txn_id' in item and 'category' in item}
            df['category'] = df['category'].mask(df['category'] == 'Uncategorised', df['txn_id'].map(category_map).fillna('Other'))

        # --- 4. AI SUMMARY GENERATION ---
        stats = {
            "total_inr": float(df[df['currency'] == 'INR']['amount'].sum()),
            "total_usd": float(df[df['currency'] == 'USD']['amount'].sum()),
            "top_merchants": df['merchant'].value_counts().head(3).to_dict(),
            "anomaly_count": int(df['is_anomaly'].sum())
        }
        
        summary_prompt = (
            "Analyze these transaction statistics and generate a concise executive summary. "
            "Return a JSON object with strictly these keys: "
            "'narrative' (string explaining spending patterns and anomalies), "
            "'risk_level' (strictly one of: 'low', 'medium', 'high'). "
            f"Stats: {json.dumps(stats)}"
        )
        
        summary_response = model.generate_content(summary_prompt)
        summary_data = json.loads(summary_response.text)

        # --- 5. HIGH-PERFORMANCE DATABASE PERSISTENCE ---
        # Save summary
        db.add(JobSummary(
            job_id=job_id,
            total_spend_inr=stats["total_inr"],
            total_spend_usd=stats["total_usd"],
            top_merchants=json.dumps(stats["top_merchants"]),
            anomaly_count=stats["anomaly_count"],
            narrative=summary_data.get('narrative', 'Analysis unavailable.'),
            risk_level=summary_data.get('risk_level', 'low')
        ))
        
        # High-speed bulk insert bypassing ORM object overhead
        transactions_to_insert = df.to_dict('records')
        for row in transactions_to_insert:
            row['job_id'] = job_id
            
        db.bulk_insert_mappings(Transaction, transactions_to_insert)
        job.row_count_raw = len(df)
        job.row_count_clean = len(df)
        job.status = "completed"
        db.commit()
        
        
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass

    except Exception as e:
        db.rollback()
        try:
            # Exponential backoff retry (5s, 10s, 20s)
            self.retry(exc=e, countdown=5 * (2 ** self.request.retries))
        except MaxRetriesExceededError:
            # Only mark as failed in DB if all retries are permanently exhausted
            job.status = "failed"
            job.error_message = str(e)
            db.commit()
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass
            raise e
    finally:
        db.close()
       
       