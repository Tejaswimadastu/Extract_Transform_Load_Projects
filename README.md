# Extract, Transform, Load (ETL) Projects

## Overview

This repository contains a collection of ETL (Extract, Transform, Load) projects designed to demonstrate real-world data engineering workflows. Each project focuses on extracting data from different sources, transforming it into a clean and structured format, and loading it for analysis and reporting.

The repository showcases data processing techniques using APIs, CSV datasets, and public data sources while following industry-standard ETL practices.

---

## Projects Included

### 1. ETL_Telco_Customer

Customer churn and telecommunications data processing pipeline.

#### Objectives
- Extract customer data
- Clean missing and inconsistent records
- Transform customer attributes
- Generate analytical datasets

#### Skills Demonstrated
- Data Cleaning
- Feature Engineering
- Customer Analytics
- Data Validation

---

### 2. ETL_Titanic

Titanic dataset ETL workflow for preprocessing and analytics.

#### Objectives
- Extract passenger data
- Handle missing values
- Transform categorical variables
- Prepare data for machine learning models

#### Skills Demonstrated
- Data Wrangling
- Feature Encoding
- Exploratory Data Analysis
- Data Transformation

---

### 3. ETL_WEATHER_API

Real-time weather data pipeline using public weather APIs.

#### Objectives
- Extract weather information through API requests
- Process JSON responses
- Transform weather metrics
- Store structured weather datasets

#### Skills Demonstrated
- API Integration
- JSON Processing
- Data Transformation
- Automated Data Collection

---

### 4. Urban_Air_Quality_ETL

Urban air quality monitoring and analytics pipeline.

#### Objectives
- Extract environmental data
- Process pollution indicators
- Analyze air quality metrics
- Generate clean analytical datasets

#### Skills Demonstrated
- Environmental Data Processing
- Data Quality Management
- ETL Automation
- Analytics Preparation

---

## Repository Structure

```text
Extract_Transform_Load_Projects/
│
├── ETL_Telco_Customer/
│   ├── Extraction
│   ├── Transformation
│   └── Loading
│
├── ETL_Titanic/
│   ├── Data Processing
│   ├── Cleaning
│   └── Feature Engineering
│
├── ETL_WEATHER_API/
│   ├── API Extraction
│   ├── JSON Processing
│   └── Data Storage
│
├── Urban_Air_Quality_ETL/
│   ├── Environmental Data
│   ├── Transformation
│   └── Reporting
│
├── image.png
└── README.md
```

---

## ETL Workflow

```text
Data Sources
      │
      ▼
Extract
      │
      ▼
Raw Data Validation
      │
      ▼
Transform
      │
      ├── Cleaning
      ├── Formatting
      ├── Standardization
      └── Feature Engineering
      │
      ▼
Load
      │
      ▼
Analytics Ready Data
```

---

## Technologies Used

### Programming Language
- Python

### Data Processing
- Pandas
- NumPy

### API Integration
- Requests

### Data Formats
- CSV
- JSON
- Excel

### Visualization
- Matplotlib
- Seaborn

### Development Tools
- Jupyter Notebook
- VS Code

---

## Key ETL Concepts Demonstrated

### Extract
- CSV Data Extraction
- API Data Retrieval
- JSON Parsing
- Data Source Connectivity

### Transform
- Missing Value Handling
- Data Cleaning
- Data Normalization
- Feature Engineering
- Data Type Conversion

### Load
- CSV Export
- Structured Dataset Creation
- Analytics-Ready Outputs

---

## Installation

### Clone Repository

```bash
git clone https://github.com/Tejaswimadastu/Extract_Transform_Load_Projects.git
cd Extract_Transform_Load_Projects
```

### Create Virtual Environment

```bash
python -m venv venv
```

Activate:

**Windows**

```bash
venv\Scripts\activate
```

**Linux/macOS**

```bash
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Learning Outcomes

This repository demonstrates:

- End-to-end ETL pipeline development
- API data extraction
- Data cleaning and transformation
- Data engineering best practices
- Analytical dataset preparation
- Real-world data processing workflows

---

## Applications

- Data Engineering
- Business Intelligence
- Data Analytics
- Machine Learning Data Preparation
- Environmental Monitoring
- Customer Analytics

---

## Future Enhancements

- Apache Airflow Integration
- Automated Scheduling
- Cloud Data Storage
- Database Loading
- Data Warehousing
- Real-Time Streaming Pipelines

---

## Author

**Tejaswi Madastu**

GitHub: https://github.com/Tejaswimadastu

---

## License

This repository is developed for educational, portfolio, and learning purposes.
