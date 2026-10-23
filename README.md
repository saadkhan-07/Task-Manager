# Task Manager – DevOps Lab Mid Exam (CSC418)

A multi-page web app with login, dashboard and task management.
**Frontend:** HTML/CSS/JS (Jinja2) · **Backend:** Python Flask + Gunicorn · **Database:** MySQL 8
Run with **Docker Compose**, deployed on **AWS EC2** behind a **Load Balancer + Auto Scaling Group**, tested with **Selenium**.

## Pages
| URL | Page | Login needed |
|---|---|---|
| `/` | Home / landing page | no |
| `/register` | Create account | no |
| `/login` | Login | no |
| `/about` | About + tech stack | no |
| `/dashboard` | Stats, progress bar, upcoming tasks | yes |
| `/tasks` | Task list with search and status filter | yes |
| `/tasks/new` | Create task | yes |
| `/tasks/<id>/edit` | Edit task | yes |
| `/api/tasks` | JSON API (your tasks) | yes |
| `/health` | Health check for the load balancer | no |

**Demo account (created automatically):** `demo` / `demo123`

## Database (MySQL)
- `users`: id, username (unique), email (unique), password_hash, created_at
- `tasks`: id, user_id (FK → users), title, description, priority (low/medium/high), status (pending/in_progress/done), due_date, created_at, updated_at

Passwords are stored hashed. Every form has a CSRF token. Users only see their own tasks.

## Project structure
```
taskmanager/
├── app/
│   ├── app.py            routes + logic (backend)
│   ├── db.py             MySQL helpers + table creation
│   ├── templates/        8 HTML pages (frontend)
│   ├── static/           style.css, main.js
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml    web + db + named volume
├── tests/test_selenium.py
├── scripts/              linux_commands.sh, install_docker_ubuntu.sh
└── aws/user-data.sh      Launch Template user data
```

## Run on your own PC first (needs Docker)
```bash
docker compose up -d --build
# open http://localhost
```

---
# Exam steps on AWS

## Step 0 – Put code on GitHub (your own repo)
```bash
git init && git add . && git commit -m "task manager"
git remote add origin https://github.com/YOUR_USERNAME/taskmanager.git
git push -u origin main
```
Edit `aws/user-data.sh` and set your repo URL.

## Step 1 – Launch ONE EC2 instance (Ubuntu 22.04, t2.micro)
Security group inbound: **22** (SSH) and **80** (HTTP). Then:
```bash
ssh -i key.pem ubuntu@<EC2_PUBLIC_IP>
```

### Task 2 – Linux (1 mark)
Run the commands in `scripts/linux_commands.sh` one by one (mkdir, ls -l, chmod, chown). Screenshot each.
(On Ubuntu the user is `ubuntu`; edit the `chown` line in the script.)

### Task 3 – Docker, Dockerfile, image, container (2 marks)
```bash
git clone https://github.com/YOUR_USERNAME/taskmanager.git && cd taskmanager
bash scripts/install_docker_ubuntu.sh
newgrp docker
docker --version
docker build -t taskmanager-web ./app
docker images
docker run -d --name test-web -p 8080:5000 taskmanager-web   # starts, DB not attached yet
docker ps
docker rm -f test-web
```

### Task 4 – Volume and persistence (1 mark)
```bash
docker compose up -d --build
docker volume ls                          # taskmanager_db_data
docker volume inspect taskmanager_db_data
```
1. Open `http://<EC2_PUBLIC_IP>`, register, log in and add the task **"Buy milk"**.
2. Remove the containers (the volume stays):
```bash
docker compose down
docker ps -a                              # containers gone
docker compose up -d
```
3. Log in again – **"Buy milk" and your account are still there.** Screenshot before and after.

### Task 5 – Docker Compose (2 marks)
```bash
docker compose ps                         # web + db running
docker compose logs web
curl http://localhost/health              # OK
```

## Step 2 – Task 6: Selenium (2 marks)
Run from your laptop (needs Google Chrome):
```bash
pip install -r tests/requirements.txt
APP_URL=http://<EC2_PUBLIC_IP> python tests/test_selenium.py
```
PowerShell:
```powershell
$env:APP_URL="http://<EC2_PUBLIC_IP>"; python tests/test_selenium.py
```
Expected: 8 tests, `Result: 8/8 tests passed` (home page, register, wrong login, login, create task, search, mark done + dashboard, logout).
Use `HEADLESS=0` to watch the browser. Run it again later with the Load Balancer DNS.

## Step 3 – Task 1: Load Balancer + Auto Scaling (2 marks)
1. **Launch Template**: Ubuntu AMI, t2.micro, same key pair and security group. Under *Advanced details → User data* paste `aws/user-data.sh`.
2. **Target Group**: type Instances, HTTP port **80**, health check path **/health**.
   - Open the target group → *Attributes* → turn on **Stickiness** (load balancer generated cookie, 1 day). **Required**, see note below.
3. **Application Load Balancer**: internet-facing, 2 availability zones, listener HTTP:80 → your target group, security group allows port 80.
4. **Auto Scaling Group**: use the Launch Template, same 2 subnets, attach the target group. Desired **2**, min **2**, max **3**. Optional: target tracking policy, average CPU 50%.
5. Wait ~5 minutes until both targets are **healthy**.
6. Open the **ALB DNS name**. The footer line "Served by container: ..." shows which instance answered. Open it in a private window to see the other one.
7. Demonstrate auto scaling: terminate one instance manually; the ASG launches a replacement.

> **Why stickiness?** Each EC2 instance runs its own MySQL container (the architecture the exam asks for), so an account created on instance A does not exist on instance B. Stickiness keeps one user on the same instance for the whole session. The `demo` account exists on every instance, so it always works. Sessions are signed with the same `SECRET_KEY` on every instance. In real production you would use one shared database (for example AWS RDS) instead; say this in the viva.

---
## Common problems
| Problem | Fix |
|---|---|
| Page not opening | Security group must allow port 80 |
| `permission denied` for docker | `newgrp docker` or log in again |
| First start is slow | MySQL needs ~20-40 s the first time; the app waits and retries |
| "Invalid CSRF token" | Reload the page (cookie expired or sticky cookie missing) |
| Targets unhealthy | Wait 5 min; health path must be `/health`; run `docker compose ps` on the instance |
| Selenium: Chrome not found | Install Google Chrome on the PC that runs the test |

## Viva cheat sheet
- **Dockerfile**: recipe for an image (base image → install packages → copy code → start command)
- **Image vs container**: image = template, container = running copy
- **Volume**: Docker-managed storage outside the container; survives `docker compose down` (but `down -v` deletes it)
- **Compose**: one YAML starts several containers; they reach each other by service name (`DB_HOST=db`)
- **depends_on + healthcheck**: web waits until MySQL is ready
- **ALB**: spreads traffic over instances and stops sending to unhealthy ones
- **ASG**: keeps the desired number of instances and replaces failed ones
- **Launch Template + user data**: blueprint and boot script for new instances
- **Selenium**: automates a real browser to test the UI
- **chmod 640**: owner read+write, group read, others nothing
- **Why Gunicorn**: Flask's built-in server is for development only
