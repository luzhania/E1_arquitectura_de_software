# Stock Market Simulator Async - Backend API

> **Academic Group Project | Backend & Cloud Architecture**

## 🔗 Project Ecosystem & Repositories

This project is built upon a distributed architecture comprising a RESTful Backend, a React Frontend, and an Asynchronous Worker service. Below are the links to the corresponding repositories:

| Component | Tech Stack | Repository URL |
|-----------|------------|----------------|
| **Backend (Core)** | FastAPI, MQTT, Docker | **[You are here](https://github.com/luzhania/E1_arquitectura_de_software)** |
| **Frontend** | React SPA, CloudFront | [🔗 Link to Frontend Repository](https://github.com/MCasakufe/ArquisisFrontend) |
| **Workers** | Celery, Redis/RabbitMQ | [🔗 Link to Workers Repository](https://github.com/Liper1/Jobmaster) |

---

## 📖 Project Overview

This is the **Backend** component of a distributed Stock Market Simulator. The system is designed to handle asynchronous stock trading, payment integrations, and real-time market updates through a robust cloud infrastructure.

### Key Features
* **Event-Driven Architecture:** Real-time processing via **MQTT** protocols for multiple channels (`stocks/info`, `requests`, `validation`, `auctions`, `updates`).
* **Asynchronous Processing:** Integration with **Celery** workers for heavy-lifting tasks and market estimations.
* **Payment Integration:** Secure payment flows using **WebPay**.
* **Serverless Components:** Utilization of **AWS Lambda** functions for specific triggers.

## 🛠️ Tech Stack & Infrastructure

### Core Application
* **Framework:** FastAPI (Python)
* **Database:** MongoDB (managed via Docker)
* **Reverse Proxy:** Nginx

### DevOps & Cloud (AWS)
* **Infrastructure as Code (IaaC):** Terraform
* **Containerization:** Docker & Docker Compose
* **CI/CD:** GitHub Actions (Automated testing and deployment)
* **Monitoring:** New Relic (APM and Infrastructure)
* **AWS Services:**
    * Compute: **EC2**
    * Storage & CDN: **S3** & **CloudFront**
    * Networking: **API Gateway** & **SSL Certificates**
    * Registry: **ECR**

## 🚀 Getting Started

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/luzhania/E1_arquitectura_de_software.git](https://github.com/luzhania/E1_arquitectura_de_software.git)
    cd E1_arquitectura_de_software
    ```

2.  **Set up environment variables:**
    Create a `.env` file.

3.  **Run with Docker Compose:**
    ```bash
    docker-compose up --build
    ```
