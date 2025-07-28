from fastapi import (
    FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Query
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse, FileResponse
from typing import List, Optional, Any
from pydantic import BaseModel, Field, EmailStr
import uuid
from pathlib import Path
import shutil
from datetime import date

app = FastAPI(
    title="Small Business Finance Manager API",
    description="APIs for finance, expenses, income, users, categories, files, reports, preferences.",
    version="1.0.0",
    openapi_tags=[
        {"name": "auth", "description": "Authentication and authorization"},
        {"name": "users", "description": "User management"},
        {"name": "roles", "description": "Role management & access control"},
        {"name": "expenses", "description": "Expense management"},
        {"name": "income", "description": "Income management"},
        {"name": "categories", "description": "Category management"},
        {"name": "budgets", "description": "Budget planning & alerts"},
        {"name": "reports", "description": "Reporting & export"},
        {"name": "dashboard", "description": "Dashboard widgets/data"},
        {"name": "preferences", "description": "User preferences"},
        {"name": "files", "description": "File/image uploads"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://vscode-internal-112-beta.beta01.cloud.kavia.ai:3000"
    ],
    allow_credentials=True,
    allow_methods=[
        "GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"
    ],
    allow_headers=["*"],
)

# ====== Dummy in-memory data stores for demonstration ========
users_db = {
    "admin@example.com": {
        "email": "admin@example.com",
        "full_name": "Admin User",
        "role": "admin",
        "hashed_password": "fakehashed",  # For demo only!
        "dark_mode": False,
        "is_active": True,
        "id": "user-1"
    }
}
roles_db = ["admin", "manager", "accountant", "employee"]
expenses_db = {}
income_db = {}
budgets_db = {}
categories_db = {}
sessions_db = {}
files_db = {}

# ============== Utility, Security & Models ===================
def fake_hash_password(password: str) -> str:
    return "fakehashed"  # Replace with real hash!

def verify_password(plain: str, hashed: str) -> bool:
    return fake_hash_password(plain) == hashed

def create_access_token(user_email: str, role: str) -> str:
    return f"TOKEN-{user_email}-{role}-{uuid.uuid4()}"  # Replace with JWT!

def get_user(email: str):
    return users_db.get(email)

class Token(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")

class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: str
    is_active: bool

class Category(BaseModel):
    id: str
    name: str

class CategoryCreate(BaseModel):
    name: str

class Expense(BaseModel):
    id: str
    title: str
    amount: float
    category_id: str
    date: date
    description: Optional[str]
    department: Optional[str]
    file_url: Optional[str]
    user_id: str

class ExpenseCreate(BaseModel):
    title: str
    amount: float
    category_id: str
    date: date
    description: Optional[str]
    department: Optional[str]

class ExpenseUpdate(BaseModel):
    title: Optional[str]
    amount: Optional[float]
    category_id: Optional[str]
    date: Optional[date]
    description: Optional[str]
    department: Optional[str]

class Income(BaseModel):
    id: str
    title: str
    amount: float
    category_id: str
    date: date
    description: Optional[str]
    department: Optional[str]
    status: str
    user_id: str

class IncomeCreate(BaseModel):
    title: str
    amount: float
    category_id: str
    date: date
    description: Optional[str]
    department: Optional[str]
    status: str = "unpaid"

class IncomeUpdate(BaseModel):
    title: Optional[str]
    amount: Optional[float]
    category_id: Optional[str]
    date: Optional[date]
    description: Optional[str]
    department: Optional[str]
    status: Optional[str]

class Budget(BaseModel):
    id: str
    category_id: str
    monthly_limit: float
    alert_threshold: float  # % or value
    user_id: str

class BudgetCreate(BaseModel):
    category_id: str
    monthly_limit: float
    alert_threshold: float

class FileUploadResponse(BaseModel):
    file_url: str
    filename: str

class DashboardCard(BaseModel):
    key: str
    title: str
    value: Any
    icon: Optional[str]
    style: Optional[dict]

class WidgetData(BaseModel):
    cards: List[DashboardCard]
    chart_data: dict

class ReportRequest(BaseModel):
    start_date: date
    end_date: date
    category_ids: Optional[List[str]]
    department: Optional[str]
    export_format: str = Field("json", description="One of: json, pdf, xlsx")

# =========== Auth/Role-Based Dependencies =====================
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

def get_current_user(token: str = Depends(oauth2_scheme)):
    # Faked token parsing
    if not token.startswith("TOKEN-"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    email = token.split("-")[1]
    user = get_user(email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

def require_role(required_roles: List[str]):
    def dependency(user=Depends(get_current_user)):
        if user["role"] not in required_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user
    return dependency

# ================= API ROUTES ================================

@app.get("/")
def health_check():
    """Health check endpoint."""
    return {"message": "Healthy"}

# ------------- AUTH ------------------------

# PUBLIC_INTERFACE
@app.post("/auth/token", response_model=Token, tags=["auth"])
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate user and return access token."""
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Incorrect credentials")
    token = create_access_token(user["email"], user["role"])
    return Token(access_token=token, token_type="bearer")

# PUBLIC_INTERFACE
@app.post("/auth/register", response_model=UserResponse, tags=["auth"])
def register(user: UserCreate):
    """Register new user account."""
    if user.email in users_db:
        raise HTTPException(status_code=400, detail="Email exists")
    uid = f"user-{uuid.uuid4()}"
    users_db[user.email] = {
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "hashed_password": fake_hash_password(user.password),
        "is_active": True,
        "id": uid,
        "dark_mode": False,
    }
    return UserResponse(**users_db[user.email])

# ------------- USERS & ROLES ---------------

# PUBLIC_INTERFACE
@app.get("/users/me", response_model=UserResponse, tags=["users"])
def get_me(user=Depends(get_current_user)):
    """Get current authenticated user."""
    return UserResponse(**user)

# PUBLIC_INTERFACE
@app.get("/users/", response_model=List[UserResponse], tags=["users"])
def list_users(user=Depends(require_role(["admin"]))):
    """List all users (admin only)."""
    return [UserResponse(**u) for u in users_db.values()]

# PUBLIC_INTERFACE
@app.get("/roles/", response_model=List[str], tags=["roles"])
def get_roles():
    """Get list of roles."""
    return roles_db

# PUBLIC_INTERFACE
@app.put("/users/{user_id}/role", response_model=UserResponse, tags=["users"])
def update_user_role(user_id: str, new_role: str, user=Depends(require_role(["admin"]))):
    """Update user's role (admin only)."""
    for dbuser in users_db.values():
        if dbuser["id"] == user_id:
            dbuser["role"] = new_role
            return UserResponse(**dbuser)
    raise HTTPException(404, detail="User not found")

# -------------- CATEGORIES -----------------

# PUBLIC_INTERFACE
@app.get("/categories/", response_model=List[Category], tags=["categories"])
def list_categories():
    """List all categories."""
    return [Category(**c) for c in categories_db.values()]

# PUBLIC_INTERFACE
@app.post("/categories/", response_model=Category, tags=["categories"])
def create_category(category: CategoryCreate, user=Depends(require_role(["admin", "manager"]))):
    """Create a new category."""
    cid = str(uuid.uuid4())
    cat = {"id": cid, "name": category.name}
    categories_db[cid] = cat
    return Category(**cat)

# PUBLIC_INTERFACE
@app.delete("/categories/{category_id}", response_model=dict, tags=["categories"])
def delete_category(category_id: str, user=Depends(require_role(["admin"]))):
    """Delete category (admin only)."""
    if category_id in categories_db:
        del categories_db[category_id]
        return {"ok": True}
    raise HTTPException(404, detail="Category not found")

# ---------- EXPENSES MANAGEMENT -------------

# PUBLIC_INTERFACE
@app.get("/expenses/", response_model=List[Expense], tags=["expenses"])
def list_expenses(
    category_id: Optional[str] = Query(None), 
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    department: Optional[str] = Query(None),
    user=Depends(get_current_user)
):
    """List expenses with optional filters."""
    results = []
    for exp in expenses_db.values():
        if exp["user_id"] != user["id"] and user["role"] != "admin":
            continue
        if category_id and exp["category_id"] != category_id:
            continue
        if department and exp.get("department") != department:
            continue
        if start_date and exp["date"] < start_date:
            continue
        if end_date and exp["date"] > end_date:
            continue
        results.append(Expense(**exp))
    return results

# PUBLIC_INTERFACE
@app.post("/expenses/", response_model=Expense, tags=["expenses"])
def create_expense(exp: ExpenseCreate, user=Depends(require_role(["admin", "manager", "accountant", "employee"]))):
    """Create new expense record."""
    eid = str(uuid.uuid4())
    expense = exp.dict()
    expense.update({"id": eid, "user_id": user["id"], "file_url": None})
    expenses_db[eid] = expense
    return Expense(**expense)

# PUBLIC_INTERFACE
@app.get("/expenses/{expense_id}", response_model=Expense, tags=["expenses"])
def get_expense(expense_id: str, user=Depends(get_current_user)):
    """Get an expense by ID."""
    exp = expenses_db.get(expense_id)
    if not exp or (exp["user_id"] != user["id"] and user["role"] != "admin"):
        raise HTTPException(404, detail="Not found")
    return Expense(**exp)

# PUBLIC_INTERFACE
@app.put("/expenses/{expense_id}", response_model=Expense, tags=["expenses"])
def update_expense(expense_id: str, changes: ExpenseUpdate, user=Depends(get_current_user)):
    """Update an expense."""
    exp = expenses_db.get(expense_id)
    if not exp or (exp["user_id"] != user["id"] and user["role"] != "admin"):
        raise HTTPException(404, detail="Not found")
    for k, v in changes.dict(exclude_unset=True).items():
        exp[k] = v
    expenses_db[expense_id] = exp
    return Expense(**exp)

# PUBLIC_INTERFACE
@app.delete("/expenses/{expense_id}", response_model=dict, tags=["expenses"])
def delete_expense(expense_id: str, user=Depends(require_role(["admin", "manager"]))):
    """Delete expense."""
    exp = expenses_db.get(expense_id)
    if not exp:
        raise HTTPException(404, detail="Not found")
    del expenses_db[expense_id]
    return {"ok": True}

# ------------- FILE UPLOAD -----------------

UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)

# PUBLIC_INTERFACE
@app.post("/files/", response_model=FileUploadResponse, tags=["files"])
def upload_file(expense_id: str = Form(...), file: UploadFile = File(...), user=Depends(get_current_user)):
    """Upload file/image for expense."""
    exp = expenses_db.get(expense_id)
    if not exp or (exp["user_id"] != user["id"] and user["role"] != "admin"):
        raise HTTPException(404, detail="Expense not found")
    fname = f"{uuid.uuid4()}_{file.filename}"
    file_path = UPLOAD_DIR / fname
    with open(file_path, "wb") as dest:
        shutil.copyfileobj(file.file, dest)
    exp["file_url"] = str(file_path.name)
    files_db[file_path.name] = {"owner": user["id"], "expense_id": expense_id}
    return FileUploadResponse(file_url=f"/files/{file_path.name}", filename=file.filename)

# PUBLIC_INTERFACE
@app.get("/files/{filename}", response_class=FileResponse, tags=["files"])
def get_uploaded_file(filename: str, user=Depends(get_current_user)):
    """Serve uploaded file/image."""
    meta = files_db.get(filename)
    if not meta:
        raise HTTPException(404, detail="File not found")
    # Simple public serving for demo
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(404)
    return FileResponse(path=str(file_path), filename=filename)

# ------------ INCOME MANAGEMENT -------------

# PUBLIC_INTERFACE
@app.get("/income/", response_model=List[Income], tags=["income"])
def list_income(
    category_id: Optional[str] = Query(None), 
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    department: Optional[str] = Query(None),
    user=Depends(get_current_user)
):
    """List income with optional filters."""
    results = []
    for inc in income_db.values():
        if inc["user_id"] != user["id"] and user["role"] != "admin":
            continue
        if category_id and inc["category_id"] != category_id:
            continue
        if department and inc.get("department") != department:
            continue
        if start_date and inc["date"] < start_date:
            continue
        if end_date and inc["date"] > end_date:
            continue
        results.append(Income(**inc))
    return results

# PUBLIC_INTERFACE
@app.post("/income/", response_model=Income, tags=["income"])
def create_income(inc: IncomeCreate, user=Depends(require_role(["admin", "manager", "accountant"]))):
    """Create new income record."""
    iid = str(uuid.uuid4())
    data = inc.dict()
    data.update({"id": iid, "user_id": user["id"]})
    income_db[iid] = data
    return Income(**data)

# PUBLIC_INTERFACE
@app.get("/income/{income_id}", response_model=Income, tags=["income"])
def get_income(income_id: str, user=Depends(get_current_user)):
    inc = income_db.get(income_id)
    if not inc or (inc["user_id"] != user["id"] and user["role"] != "admin"):
        raise HTTPException(404, detail="Not found")
    return Income(**inc)

# PUBLIC_INTERFACE
@app.put("/income/{income_id}", response_model=Income, tags=["income"])
def update_income(income_id: str, changes: IncomeUpdate, user=Depends(get_current_user)):
    inc = income_db.get(income_id)
    if not inc or (inc["user_id"] != user["id"] and user["role"] != "admin"):
        raise HTTPException(404, detail="Not found")
    for k, v in changes.dict(exclude_unset=True).items():
        inc[k] = v
    income_db[income_id] = inc
    return Income(**inc)

# ------------- BUDGET PLANNING --------------

# PUBLIC_INTERFACE
@app.get("/budgets/", response_model=List[Budget], tags=["budgets"])
def list_budgets(user=Depends(get_current_user)):
    """List all budgets created by the user."""
    return [Budget(**b) for b in budgets_db.values() if b["user_id"] == user["id"] or user["role"] == "admin"]

# PUBLIC_INTERFACE
@app.post("/budgets/", response_model=Budget, tags=["budgets"])
def create_budget(budget: BudgetCreate, user=Depends(require_role(["admin", "manager"]))):
    """Create a new budget plan."""
    bid = str(uuid.uuid4())
    bud = budget.dict()
    bud.update({"id": bid, "user_id": user["id"]})
    budgets_db[bid] = bud
    return Budget(**bud)

# PUBLIC_INTERFACE
@app.delete("/budgets/{budget_id}", response_model=dict, tags=["budgets"])
def delete_budget(budget_id: str, user=Depends(require_role(["admin", "manager"]))):
    """Delete a budget plan."""
    if budget_id in budgets_db:
        del budgets_db[budget_id]
        return {"ok": True}
    raise HTTPException(404, detail="Budget not found")

# ------------ DASHBOARD & SIDEBAR -----------

# PUBLIC_INTERFACE
@app.get("/dashboard/widgets", response_model=WidgetData, tags=["dashboard"])
def dashboard_data(user=Depends(get_current_user)):
    """Get cards/charts data for dashboard."""
    # Dummy static example
    cards = [
        DashboardCard(key="total_expense", title="Total Expenses", value=round(sum([e["amount"] for e in expenses_db.values()]),2), icon="💸"),
        DashboardCard(key="total_income", title="Total Income", value=round(sum([i["amount"] for i in income_db.values()]),2), icon="💰"),
    ]
    chart_data = {
        "expenses_by_month": {},
        "income_by_month": {},
    }
    # Build basic chart data (aggregation)
    for e in expenses_db.values():
        m = str(e["date"].month)
        chart_data["expenses_by_month"].setdefault(m, 0)
        chart_data["expenses_by_month"][m] += e["amount"]
    for i in income_db.values():
        m = str(i["date"].month)
        chart_data["income_by_month"].setdefault(m, 0)
        chart_data["income_by_month"][m] += i["amount"]
    data = WidgetData(cards=cards, chart_data=chart_data)
    return data

# PUBLIC_INTERFACE
@app.get("/sidebar/routes", response_model=List[str], tags=["dashboard"])
def get_sidebar_routes(user=Depends(get_current_user)):
    """Get available navigation routes for the sidebar."""
    base_routes = ["/dashboard", "/expenses", "/income", "/budgets", "/reports", "/settings"]
    if user["role"] == "admin":
        base_routes += ["/users", "/categories"]
    if user["role"] in ["admin", "manager"]:
        base_routes += ["/budgets"]
    return base_routes

# ---------- USER PREFERENCES (Dark Mode) -----
class UserPreferences(BaseModel):
    dark_mode: bool

# PUBLIC_INTERFACE
@app.get("/preferences", response_model=UserPreferences, tags=["preferences"])
def get_preferences(user=Depends(get_current_user)):
    """Get user preferences/settings."""
    return UserPreferences(dark_mode=user.get("dark_mode", False))

# PUBLIC_INTERFACE
@app.put("/preferences", response_model=UserPreferences, tags=["preferences"])
def set_preferences(prefs: UserPreferences, user=Depends(get_current_user)):
    """Set user preferences/settings."""
    users_db[user["email"]]["dark_mode"] = prefs.dark_mode
    return prefs

# -------------- REPORTS/EXPORT ---------------
import io

# PUBLIC_INTERFACE
@app.post("/reports/export", tags=["reports"])
def report_export(req: ReportRequest, user=Depends(require_role(["admin", "manager", "accountant"]))):
    """
    Export financial data (expenses/incomes) in chosen format.
    Formats supported: json, pdf, xlsx
    """
    # Filter relevant data
    filtered_expenses = [
        e for e in expenses_db.values()
        if (not req.category_ids or e["category_id"] in req.category_ids)
        and (not req.department or e.get("department")==req.department)
        and e["date"] >= req.start_date and e["date"] <= req.end_date
    ]
    filtered_income = [
        i for i in income_db.values()
        if (not req.category_ids or i["category_id"] in req.category_ids)
        and (not req.department or i.get("department")==req.department)
        and i["date"] >= req.start_date and i["date"] <= req.end_date
    ]
    # Format output
    if req.export_format == "json":
        return {"expenses": filtered_expenses, "income": filtered_income}
    elif req.export_format == "pdf":
        pdf_stream = io.BytesIO(b"%PDF-1.4\n...DUMMY PDF CONTENT\n")
        return StreamingResponse(pdf_stream, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=report.pdf"})
    elif req.export_format == "xlsx":
        xls_stream = io.BytesIO(b"PK...\nDUMMY XLSX CONTENT\n")
        return StreamingResponse(xls_stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=report.xlsx"})
    else:
        raise HTTPException(status_code=400, detail="Invalid format")

# ----------- FINISHED MAIN -------------------

