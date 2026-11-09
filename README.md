# NiDi: An AI-Powered Multilingual Legal Chatbot and Crime Assistance Platform

NiDi is a comprehensive digital legal and safety assistant designed for Indian citizens. It bridges the gap between complex legal frameworks (such as the IPC and the new BNS) and everyday citizens by providing simplified explanations, multilingual support, crime analytics, and an emergency police locator.

---

## 🚀 Key Features

- **Hybrid AI Architecture:** Combines **Rasa Open Source** for deterministic NLU intent management with **Llama 3.3 (via Groq LPU)** for generative, simplified legal reasoning.
- **Multilingual Support:** Offers seamless trilingual interaction in **English, Hindi, and Malayalam** using `langdetect` and `deep-translator`.
- **Emergency Police Locator:** Integrates with the **OpenStreetMap Overpass API** and **Leaflet.js** to find and map the nearest police stations based on live GPS coordinates.
- **Legal Complaint Drafting:** Guides users through structured incident reporting and automatically generates formal legal drafts addressed to the Station House Officer (SHO).
- **Crime Intelligence Dashboard:** Displays interactive charts and analytics built with **Pandas** and **Plotly** using data stored in **MongoDB Atlas**.
- **Secure Authentication:** Implements **Google OAuth 2.0** for secure, passwordless user sign-in.

---

## 🛠️ Tech Stack & Libraries

- **Backend / Web Framework:** Python, Flask
- **NLP & AI Engine:** Rasa Open Source, Llama 3.3 (Groq Cloud API)
- **Database:** MongoDB Atlas (via PyMongo)
- **Data Analysis & Visualization:** Pandas, Plotly, BeautifulSoup, Selenium
- **Geospatial & Navigation:** OpenStreetMap Overpass API, Leaflet.js, Haversine Formula
- **Multilingual Pipeline:** Deep-Translator, Langdetect
- **Security & Auth:** Google OAuth 2.0, Python-Dotenv

---

## ⚙️ Installation & Setup

1. **Clone the Repository:**
   ```bash
   git clone [https://github.com/your-username/nidi-legal-assistant.git](https://github.com/your-username/nidi-legal-assistant.git)
   cd nidi-legal-assistant
