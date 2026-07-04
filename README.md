# 🚀 Alemeno AI-Powered Transaction Processing Pipeline

An asynchronous, high-performance financial transaction processing and anomaly detection engine built for the **Alemeno Backend + DevOps Internship Assignment**.

This backend system ingests dirty financial transaction CSVs, cleans and normalizes the data vectorially using **Pandas**, detects statistical and regional anomalies, classifies uncategorized spending using **Google Gemini AI**, and generates an executive risk narrative—all processed asynchronously through a background job queue.

---

## 📋 Table of Contents

1. [Project Overview & Capabilities](#1-project-overview--capabilities)
2. [Step-by-Step Setup Guide (For Evaluators)](#2-step-by-step-setup-guide-for-evaluators)
3. [Complete API Reference & Example Curl Requests](#3-complete-api-reference--example-curl-requests)
4. [Deep Dive: How the Asynchronous Pipeline Works](#4-deep-dive-how-the-asynchronous-pipeline-works)
5. [Database Schema & Data Model](#5-database-schema--data-model)
6. [System Architecture & Data Flow](#6-system-architecture--data-flow)
7. [100x Scale & Bottleneck Analysis](#7-100x-scale--bottleneck-analysis)
8. [Submission Artifacts Checklist](#8-submission-artifacts-checklist)

---

## 1. Project Overview & Capabilities

Financial transaction data is rarely clean in the real world. This project solves the challenge of processing "dirty" exported payment data at scale without blocking HTTP client requests.

### ✨ Key Features:

- **Asynchronous Ingestion:** Files are uploaded via FastAPI and handed off to Redis/Celery immediately, ensuring instant API response times.
- **Vectorized Data Cleaning:** Replaced slow row-by-row iteration with vectorized Pandas operations for currency sanitization, date normalization, and deduplication.
- **Intelligent Anomaly Detection:** Flags statistical outliers ($>3\times$ account median) and regional currency discrepancies (e.g., USD billing on domestic Indian platforms like Swiggy/Ola/IRCTC).
- **AI Categorization & Risk Summarization:** Uses Google Gemini AI with strict JSON schema enforcement to categorize unknown merchants and generate an executive risk level (`low`, `medium`, `high`).
- **High-Speed Database Persistence:** Leverages SQLAlchemy bulk mapping insertions to write thousands of rows to PostgreSQL in fractions of a second.

---

## 2. Step-by-Step Setup Guide (For Evaluators)

This repository is **100% containerized** using Docker Compose. You do not need to install Python, PostgreSQL, or Redis on your local machine.

### Step 1: Clone the Repository

Open your terminal and clone the project:

```bash
git clone <your-github-repo-url>
cd alemeno
```

cp .env.example .env

# Database & Cache Connection Strings (Docker Compose default hostnames)

DATABASE_URL=postgresql://postgres:postgres@db:5432/alemenodb
REDIS_URL=redis://redis:6379/0

# REQUIRED: Insert your Google Gemini API Key below

GEMINI_API_KEY=your_actual_gemini_api_key_here
docker compose up --build -d
docker compose ps
