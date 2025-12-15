# Project Setup & Core Features

## Implemented Features

**Load Balancer**  
Random traffic distribution across local fog nodes.

**Monitoring & Observability**  
Prometheus integrated for metrics collection.  
Metrics are visualized using Grafana dashboards.

**Client Simulation Interface**  
Web-based interface built with Flask Framework to simulate client requests.

## Getting Started

### 1. Activate the Virtual Environment
Make sure you are inside the project directory, then activate the virtual environment:

### 2. Install Project Dependencies
Install all required Python packages using:

pip install -r requirements.txt

### 3. Run Prometheus
Ensure Prometheus is added to your system PATH, then start it with:
prometheus --config.file=prometheus.yml
For detailed configuration of Prometheus as a Grafana data source, refer to:
https://grafana.com/docs/grafana/latest/datasources/prometheus/configure/
            
