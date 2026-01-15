import os
import bcrypt
import razorpay
import uuid
import smtplib
from datetime import date, datetime, timedelta
from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from ai import generate_listing, generate_keywords
from db import get_connection
from jose import jwt, JWTError
from datetime import datetime, timedelta
from pydantic import BaseModel
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi.responses import FileResponse

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")





# ================= RAZORPAY CONFIG =================
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")



 
razorpay_client = razorpay.Client(
    auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
)

# ================= JWT CONFIG =================
SECRET_KEY = os.getenv("JWT_SECRET","SELLERGEN_AI_SECRET_2026")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def send_email(to_email, subject, message):
    msg = MIMEMultipart()
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(message, "html"))

    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(SMTP_EMAIL, SMTP_PASSWORD)
    server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
    server.quit()

def verify_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Token missing")
    try:
        scheme, token = authorization.split()
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    



def admin_only(user=Depends(verify_token)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    return user



# ================= USAGE LIMIT =================
FREE_LIMIT = 5


def check_user_usage(email: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_plan, usage_count, last_used 
        FROM users WHERE email = ?
    """, email)

    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=401, detail="User not found")

    plan, usage, last_used = row
    today = date.today()

    if last_used is None or last_used != today:
        usage = 0
        cursor.execute("""
            UPDATE users SET usage_count = 0, last_used = ?
            WHERE email = ?
        """, today, email)

    if plan == "pro":
        conn.commit()
        conn.close()
        return

    if usage >= FREE_LIMIT:
        conn.close()
        raise HTTPException(status_code=429, detail="Free limit reached. Please upgrade.")

    cursor.execute("""
        UPDATE users SET usage_count = usage_count + 1
        WHERE email = ?
    """, email)

    conn.commit()
    conn.close()


def save_usage_log(email: str, action: str, input_text: str, output_text: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO usage_logs (email, action_type, input_text, output_text)
        VALUES (?, ?, ?, ?)
    """, (email, action, input_text, output_text))
    conn.commit()
    conn.close()



# ================= APP INIT =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

app = FastAPI(title="SellerGen AI")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
# ================= UI ROUTES =================
@app.get("/", response_class=HTMLResponse)
def home():
    return open(os.path.join(FRONTEND_DIR, "index.html"), encoding="utf-8").read()

@app.get("/signup", response_class=HTMLResponse)
def signup_page():
    return open(os.path.join(FRONTEND_DIR, "signup.html"), encoding="utf-8").read()

@app.get("/login", response_class=HTMLResponse)
def login_page():
    return open(os.path.join(FRONTEND_DIR, "login.html"), encoding="utf-8").read()

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return open(os.path.join(FRONTEND_DIR, "dashboard.html"), encoding="utf-8").read()

@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return open(os.path.join(FRONTEND_DIR, "admin.html"), encoding="utf-8").read()

@app.get("/users", response_class=HTMLResponse)
def users_page():
    return open(os.path.join(FRONTEND_DIR, "users.html"), encoding="utf-8").read()


@app.get("/upgrade", response_class=HTMLResponse)
def upgrade():
    return open(os.path.join(FRONTEND_DIR, "upgrade.html"), encoding="utf-8"). read()


@app.get("/reset-password/{token}", response_class=HTMLResponse)
def reset_page(token: str):
    return open(os.path.join(FRONTEND_DIR, "reset_password.html"), encoding="utf-8").read()


@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page():
    return open(os.path.join(FRONTEND_DIR, "forgot_password.html"), encoding="utf-8").read()





# ================= DATA MODELS =================
class ListingRequest(BaseModel):
    product_name: str
    category: str
    features: str
    template: str
    language: str
   


class KeywordRequest(BaseModel):
    product: str
    


class SignupRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class PaymentSuccess(BaseModel):
    email: str
    payment_id: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

# ================= AI ROUTES (PROTECTED) =================
@app.post("/generate-listing")
def generate(data: ListingRequest, user=Depends(verify_token)):
    email = user["sub"]
    check_user_usage(email)

    result = generate_listing(
        data.product_name,
        data.category,
        data.features,
        data.template,
        data.language
    )

    # 🔥 yahan output_text add kar diya
    save_usage_log(
        email,
        "listing",
        f"{data.product_name} | {data.category}",
        result
    )

    return {"output": result}



@app.post("/generate-keywords")
def generate_keywords_api(data: KeywordRequest, user=Depends(verify_token)):
    email = user["sub"]
    check_user_usage(email)

    result = generate_keywords(data.product)

    # 🔥 yahan bhi output_text add
    save_usage_log(
        email,
        "keywords",
        data.product,
        result
    )

    return {"output": result}



# ================= AUTH ROUTES =================
@app.post("/signup")
def signup(data: SignupRequest):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE email = ?", data.email)
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="User already exists")

    hashed_password = bcrypt.hashpw(
        data.password.encode("utf-8"),
        bcrypt.gensalt()
    )

    cursor.execute("""
        INSERT INTO users (email, password, user_plan, usage_count, last_used)
        VALUES (?, ?, 'free', 0, GETDATE())
    """, data.email, hashed_password.decode("utf-8"))

    conn.commit()
    conn.close()
    return {"message": "Signup successful"}


@app.post("/login")
def login(data: LoginRequest):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT password, user_plan, role  FROM users WHERE email = ?
    """, data.email)

    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=400, detail="User not found")

    db_password, user_plan, role = row 

    if not bcrypt.checkpw(
        data.password.encode("utf-8"),
        db_password.encode("utf-8")
    ):
        raise HTTPException(status_code=400, detail="Wrong password")

    token = create_access_token({
        "sub": data.email,
        "plan": user_plan,
        "role": role
    })

    return {
        "message": "Login successful",
        "token": token,
        "plan": user_plan,
        "role": role 
    }


# ================= USAGE API =================
@app.get("/usage")
def get_usage(user=Depends(verify_token)):
    email = user["sub"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_plan, usage_count FROM users WHERE email = ?
    """, email)

    row = cursor.fetchone()
    conn.close()

    plan, used = row
    if plan == "pro":
        return {"plan": "pro", "used": used, "limit": "unlimited"}
    else:
        return {"plan": "free", "used": used, "limit": FREE_LIMIT}


# ================= HISTORY API =================
@app.get("/history")
def get_history(user=Depends(verify_token)):
    email = user["sub"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT action_type, input_text, output_text, created_at
        FROM usage_logs
        WHERE email = ?
        ORDER BY created_at DESC
    """, email)

    rows = cursor.fetchall()
    conn.close()

    history = []
    for r in rows:
        history.append({
            "action": r[0],
            "input": r[1],
            "output": r[2],   # 🔥 yeh new field
            "time": r[3].strftime("%d-%m-%Y %H:%M")
        })

    return history



# ================= PAYMENT (TEST MODE) =================
@app.post("/create-order")
def create_order():
    return {
        "id": "order_test_12345",
        "amount": 19900,
        "currency": "INR"
    }


@app.post("/verify-payment")
def verify_payment(user=Depends(verify_token)):
    email = user["sub"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users SET user_plan = 'pro'
        WHERE email = ?
    """, email)

    conn.commit()
    conn.close()

    return {"status": "success", "message": "Pro plan activated"}

@app.get("/admin/stats")

def admin_stats(user=Depends(admin_only)):
    conn = get_connection()
    cursor = conn.cursor()

    # Total users
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    # Free users
    cursor.execute("SELECT COUNT(*) FROM users WHERE user_plan = 'free'")
    free_users = cursor.fetchone()[0]

    # Pro users
    cursor.execute("SELECT COUNT(*) FROM users WHERE user_plan = 'pro'")
    pro_users = cursor.fetchone()[0]

    # Active today
    today = date.today()
    cursor.execute("""
        SELECT COUNT(*) FROM users 
        WHERE CAST(last_used AS DATE) = ?
    """, today)
    active_today = cursor.fetchone()[0]

    conn.close()

    return {
        "total_users": total_users,
        "free_users": free_users,
        "pro_users": pro_users,
        "active_today": active_today
    }
    
@app.get("/admin/users")
def admin_stats(user=Depends(admin_only)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, email, user_plan, usage_count, last_used
        FROM users
        ORDER BY id DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    users = []
    for r in rows:
        users.append({
            "id": r[0],
            "email": r[1],
            "plan": r[2],
            "usage": r[3],
            "last_used": r[4].strftime("%d-%m-%Y") if r[4] else "Never"
        })

    return users

@app.get("/admin/chart-data")
def admin_stats(user=Depends(admin_only)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users WHERE user_plan='free'")
    free = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE user_plan='pro'")
    pro = cursor.fetchone()[0]

    today = date.today()
    cursor.execute("""
        SELECT COUNT(*) FROM users 
        WHERE CAST(last_used AS DATE) = ?
    """, today)
    active_today = cursor.fetchone()[0]

    conn.close()

    return {
        "free": free,
        "pro": pro,
        "active_today": active_today
    }

# ================= ADMIN ACTION APIs =================

@app.post("/admin/set-plan/{id}")
def set_plan(id: int, plan: str, user=Depends(admin_only)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users SET user_plan = ?
        WHERE id = ?
    """, (plan, id))

    conn.commit()
    conn.close()

    return {"status": "success", "message": f"User plan updated to {plan}"}

@app.delete("/admin/delete-user/{id}")
def delete_user(id: int, user=Depends(admin_only)):
    conn = get_connection()
    cursor = conn.cursor()

    # पहले user के logs delete करो (foreign key issues से बचने के लिए)
    cursor.execute("DELETE FROM usage_logs WHERE email = (SELECT email FROM users WHERE id = ?)", (id,))
    cursor.execute("DELETE FROM users WHERE id = ?", (id,))

    conn.commit()
    conn.close()

    return {"status": "success", "message": "User deleted successfully"}



@app.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest):
    email = data.email

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return {"message": "If email exists, reset link has been sent"}

    token = str(uuid.uuid4())
    expiry = datetime.utcnow() + timedelta(minutes=30)

    cursor.execute("""
        UPDATE users 
        SET reset_token=?, reset_token_expiry=?
        WHERE email=?
    """, (token, expiry, email))

    conn.commit()
    conn.close()

    BASE_URL = "http://10.17.66.75:8000"

    reset_link = f"{BASE_URL}/reset-password/{token}"

    email_body = f"""
    <h3>Password Reset</h3>
    <p>Click the link below to reset your password:</p>
    <a href="{reset_link}">{reset_link}</a>
    <p>This link is valid for 30 minutes.</p>
    """

    send_email(
        email,
        "SellerGen AI - Password Reset",
        email_body
    )

    return {"message": "Reset link sent to email"}

