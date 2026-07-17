
# Company Infrastructure & Administrative Facts

*   **Standard Operating System:** All virtual machines and servers in our production environment run Ubuntu Server 22.04 LTS.
*   **Database Server (Production):** `db-prod.internal` (IP: `10.0.2.15`, Default PostgreSQL Port: `5432`).
*   **Web Server (Nginx Frontend):** `web-frontend.internal` (IP: `10.0.2.10`, Default Ports: `80`, `443`).
*   **Application Directory:** The source code of our web applications is always located in `/var/www/html/app/`.
*   **Deployment User:** All automated deployments and CI/CD operations are executed using the `deployer` service user, not `root`.