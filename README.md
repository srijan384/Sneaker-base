# 👟 Sneaker Base – Honeypot E-Commerce Website

![Docker](https://img.shields.io/badge/Docker-Containerized-blue?logo=docker)
![CI/CD Pipeline](https://github.com/srijan384/Sneaker-base/actions/workflows/main.yml/badge.svg)


Sneaker Base is a honeypot-based e-commerce web application developed as part of the ETT (Emerging Technology Trends). The project simulates a real sneaker shopping platform while integrating a security mechanism to detect and trap bot activity. The system ensures that genuine users experience a normal e-commerce interface, while bots are redirected into a controlled fake environment.

The primary objective of this project is to combine web development with cybersecurity concepts. It focuses on detecting automated or suspicious traffic and misleading it using a honeypot mechanism. Once a bot is detected, it is redirected to a fake version of the website where synthetic data is served, preventing access to real system functionality.

The honeypot system works by differentiating between human users and bots based on behavior. Human users can browse products, view details, add items to cart, and manage wishlists. Bots, on the other hand, are trapped in a fake environment where all the displayed data is dynamically generated and has no real value.

The application includes standard e-commerce features such as product listings with pagination, product detail pages, cart functionality, wishlist management, and session-based tracking. In addition, it incorporates a security layer that detects bots and redirects them to a fake interface.

Fake data generation is implemented using the Python Faker library. It generates random product names, prices, and other synthetic information, ensuring that bots interact only with non-real data. This keeps malicious systems engaged without exposing actual application logic or data.

The project is built using HTML, CSS, and JavaScript for the frontend, and Python with Flask for the backend. The Faker library is used for generating synthetic data. From a DevOps perspective, the application is containerized using Docker, managed using Docker Compose, served in production using Gunicorn, and integrated with a CI/CD pipeline using GitHub Actions.

The workflow of the system can be summarized as:
User → Website → Bot Detection → Honeypot Redirect → Fake Data Environment

To run the project using Docker:
docker-compose up --build

Then open:
http://localhost:5001

To run the project locally without Docker:
pip install -r requirements.txt
python app.py

Project structure:
SNEAKER-BASE/
│
├── app.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env
│
├── static/
├── templates/
└── assets/

Team Members:
Rhea Ahuja 
23fe10cse00505
Srijan Singh
23fe10cse00522

Through this project, we gained an understanding of honeypot-based security systems, Flask web development, fake data generation using Faker, and practical implementation of DevOps tools like Docker and CI/CD pipelines.

Future improvements may include advanced bot detection using machine learning, integration with a database, deployment on cloud platforms like AWS or Azure, and adding a real-time monitoring dashboard.

This project demonstrates how cybersecurity concepts like honeypots can be effectively integrated into modern web applications along with DevOps practices to build scalable and secure systems.