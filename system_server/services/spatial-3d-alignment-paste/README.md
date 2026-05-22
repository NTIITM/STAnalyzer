# PASTE 3D Bioinformatics Service - Example Deployment Package

This is an example service package prepared for the STAnalyzer platform. It demonstrates how to wrap a Python script into an HTTP API using FastAPI, and register it to the platform for public access.

This service wraps the **PASTE** (Probabilistic Alignment of Spatial Transcriptomics Experiments) algorithm, designed for pairwise or 3D alignment analysis of multiple spatial transcriptomics (ST) slices.

---

## 1. Deployment (via Docker)

To ensure an isolated execution environment and one-click deployment, we recommend deploying via Docker. A `Dockerfile` and `docker-compose.yml` are provided in this package.

### Steps
1. Prepare a **publicly accessible server** (with a public IP address).
2. Ensure `docker` and `docker-compose` are installed on your server.
3. Open a terminal in the directory containing `docker-compose.yml`, and run:
```bash
docker-compose up -d --build
```
4. Once the image is built and the container starts, the service will be exposed on port `51805` of your server. You can check the execution status using `docker ps` or `docker-compose logs -f`.

*Note: The application will automatically map the `outputs` directory in the current path to store generated images and logs.*

---

## 2. Register Your Service on STAnalyzer

Once your service is running on your **public server** (e.g., `http://your-server-public-ip:51805`), you can register it on the STAnalyzer frontend so it can be incorporated into unified data analysis workflows.

1. Open the STAnalyzer frontend, and navigate to **Help -> Service Management**.
2. Click **Create Service** in the top right corner.
3. On the right side of the page, locate the **"Import via Configuration"** area.
4. Upload the **`service_config.json`** file included in this package.
5. The form will automatically populate all necessary details (including Name, APIs, Parameters, and File configs).
6. **CRITICAL**: The **Base URL** field in the form must be updated. You **MUST** change it to point to your actual public server IP and port (e.g., `http://8.130.x.x:51805`). **Do not use localhost or 127.0.0.1**, as the STAnalyzer platform needs to securely communicate with your service over the internet.
7. Click Save. Your PASTE 3D alignment service is now registered and available on STAnalyzer!
