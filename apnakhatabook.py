import streamlit as st
import sqlite3
from datetime import datetime
import pandas as pd

# -----------------------------
# Database Setup
# -----------------------------
conn = sqlite3.connect("lendenwebapp.db", check_same_thread=False)
c = conn.cursor()

# Users table
c.execute('''CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT,
                role TEXT
            )''')

# Records table
c.execute('''CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_username TEXT,
                received REAL DEFAULT 0,
                paid_out REAL DEFAULT 0,
                datetime TEXT,
                payee TEXT,
                total_paid REAL DEFAULT 0,
                total_received REAL DEFAULT 0,
                note TEXT DEFAULT ''
            )''')
conn.commit()


# -----------------------------
# Default Admin Account
# -----------------------------
def ensure_admin():
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                  ("admin", "vinsolit", "admin"))
        conn.commit()
ensure_admin()


# -----------------------------
# Helper Functions
# -----------------------------
def add_user(username, password):
    try:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, "user"))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def verify_user(username, password):
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    return c.fetchone()


def get_records(owner):
    c.execute("SELECT * FROM records WHERE owner_username=?", (owner,))
    return c.fetchall()


def update_record(owner, received, paid_out, payee, note=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c.execute("SELECT * FROM records WHERE owner_username=? AND payee=? ORDER BY id DESC LIMIT 1", (owner, payee))
    last_record = c.fetchone()

    if last_record:
        prev_total_received = last_record[7]
        prev_total_paid = last_record[6]
    else:
        prev_total_received = 0
        prev_total_paid = 0

    new_total_received = prev_total_received + received - paid_out
    if new_total_received < 0:
        new_total_received = 0
    new_total_paid = prev_total_paid + paid_out

    c.execute('''INSERT INTO records 
                 (owner_username, received, paid_out, datetime, payee, total_paid, total_received, note)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (owner, received, paid_out, now, payee, new_total_paid, new_total_received, note))
    conn.commit()


def get_all_records(role):
    if role == "admin":
        c.execute("SELECT * FROM records")
        return c.fetchall()
    return []


def delete_user(username):
    c.execute("DELETE FROM users WHERE username=?", (username,))
    c.execute("DELETE FROM records WHERE owner_username=?", (username,))
    conn.commit()


# -----------------------------
# CSV Generator (All Payee Histories)
# -----------------------------
def generate_csv(username):
    c.execute("SELECT payee FROM records WHERE owner_username=? GROUP BY payee", (username,))
    payees = [p[0] for p in c.fetchall()]
    all_data = []
    for payee in payees:
        c.execute("SELECT received, paid_out, datetime, note FROM records WHERE owner_username=? AND payee=? ORDER BY datetime ASC",
                  (username, payee))
        recs = c.fetchall()
        total_received = 0
        total_paid = 0
        for r in recs:
            received = float(r[0] or 0)
            paid = float(r[1] or 0)
            total_received += received - paid
            total_paid += paid
            all_data.append({
                "Payee": payee,
                "Received": received,
                "Paid": paid,
                "Balance": total_received,
                "Total Paid": total_paid,
                "Date": r[2],
                "Note": r[3]
            })
    df = pd.DataFrame(all_data)
    return df.to_csv(index=False).encode('utf-8')


# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="LenDenWebApp 💰", layout="centered")

# Custom CSS
st.markdown("""
    <style>
    .stApp {background: linear-gradient(135deg, #FFDAB9, #E0FFFF); font-family: 'Arial Black', sans-serif;}
    .title {text-align:center; font-size:45px; font-weight:bold; color:#FF4500; text-shadow:2px 2px 5px #FFA07A;}
    .sub {text-align:center; font-size:20px; font-weight:bold; color:#008B8B; text-shadow:1px 1px 3px #20B2AA;}
    .green-bold {color:#008000; font-weight:bold; background-color:#E0FFE0; padding:2px 5px; border-radius:5px;}
    .red-bold {color:#FF0000; font-weight:bold; background-color:#FFE0E0; padding:2px 5px; border-radius:5px;}
    .form-button-green {background-color:#32CD32 !important; color:white !important; font-weight:bold; border-radius:5px; height:40px;}
    .form-button-blue {background-color:#1E90FF !important; color:white !important; font-weight:bold; border-radius:5px; height:40px;}
    .stTextInput>div>div>input {border-radius:10px; border:2px solid #20B2AA;}
    .stNumberInput>div>div>input {border-radius:10px; border:2px solid #20B2AA;}
    .developer-sign {position: fixed; top: 10px; right: 20px; font-weight:bold; color:#8B0000; z-index:999;}
    </style>
""", unsafe_allow_html=True)

st.markdown("<div class='title'>💰 LenDenWebApp</div>", unsafe_allow_html=True)
st.markdown("<div class='sub'>Simple and Secure Record Management</div>", unsafe_allow_html=True)
st.markdown("<div class='developer-sign'>Developed By: Mool Chandra Vishwakarma</div>", unsafe_allow_html=True)
st.write("---")


# -----------------------------
# Auth
# -----------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None

if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Signup"])
    with tab1:
        st.subheader("Login")
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Login"):
            user = verify_user(u, p)
            if user:
                st.session_state.logged_in = True
                st.session_state.username = user[0]
                st.session_state.role = user[2]
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid credentials")

    with tab2:
        st.subheader("Signup")
        nu = st.text_input("New Username")
        np = st.text_input("New Password", type="password")
        if st.button("Signup"):
            if add_user(nu, np):
                st.success("Account created!")
            else:
                st.error("Username already exists")

else:
    st.sidebar.title("Menu")
    st.sidebar.write(f"👤 `{st.session_state.username}` ({st.session_state.role})")
    menu = st.sidebar.radio("Navigate", ["My Record", "All Records", "Manage Users", "Logout"])

    if menu == "My Record":
        st.header("💼 My Record")

        user_records = get_records(st.session_state.username)
        if user_records:
            payees_seen = set()
            for rec in user_records:
                if rec[5] in payees_seen:
                    continue
                payees_seen.add(rec[5])
                c.execute("SELECT SUM(received), SUM(paid_out), MAX(datetime), id FROM records WHERE owner_username=? AND payee=? ORDER BY id DESC",
                          (st.session_state.username, rec[5]))
                sums = c.fetchone()
                total_received = (sums[0] or 0) - (sums[1] or 0)
                total_paid = sums[1] or 0
                last_time = sums[2] or ""
                st.markdown(
                    f"🧾 **Payee:** {rec[5]} | "
                    f"<span class='green-bold'>💰 Balance: Rs.{total_received:.2f}</span> | "
                    f"<span class='red-bold'>💸 Paid: Rs.{total_paid:.2f}</span> | 🕒 {last_time}",
                    unsafe_allow_html=True
                )
                with st.expander(f"Show History for {rec[5]}", expanded=False):
                    c.execute("SELECT id, received, paid_out, datetime, note FROM records WHERE owner_username=? AND payee=? ORDER BY datetime ASC",
                              (st.session_state.username, rec[5]))
                    history = c.fetchall()
                    if history:
                        for h in history:
                            st.write(f"Received: Rs.{h[1]:.2f}, Paid: Rs.{h[2]:.2f}, Note: {h[4]}, Date: {h[3]}")

        # ✅ CSV Download Button (All Payee Histories)
        csv_data = generate_csv(st.session_state.username)
        st.download_button("📄 Download All Records (CSV)", csv_data, file_name="All_Records.csv", mime="text/csv")

        # ✅ Add Record Form with Note
        with st.form("update_record_form"):
            received = st.number_input("Add Received Amount", min_value=0.0, step=0.01)
            paid_out = st.number_input("Add Paid Out Amount", min_value=0.0, step=0.01)
            payee = st.text_input("Payee Name")
            note = st.text_input("Note (optional)")  # <— Added Note Field

            col1, col2 = st.columns([1, 1])
            with col1:
                submitted = st.form_submit_button("Update Record")
            with col2:
                calc = st.form_submit_button("Calculate")

            if submitted:
                if not payee.strip():
                    st.warning("Enter payee name.")
                else:
                    update_record(st.session_state.username, received, paid_out, payee.strip(), note)
                    st.success("Record added!")
                    st.rerun()

            if calc:
                st.info(f"Total = Rs.{received + paid_out:.2f}")

    elif menu == "All Records":
        if st.session_state.role == "admin":
            st.header("📋 All Records")
            recs = get_all_records(st.session_state.role)
            if recs:
                for r in recs:
                    st.markdown(
                        f"👤 {r[1]} | Payee: {r[5]} | "
                        f"<span class='green-bold'>💰 Balance: Rs.{r[7]:.2f}</span> | "
                        f"<span class='red-bold'>💸 Paid: Rs.{r[6]:.2f}</span> | 🕒 {r[4]}",
                        unsafe_allow_html=True
                    )
            else:
                st.info("No records found.")
        else:
            st.warning("You’re not authorized to view this page.")

    elif menu == "Manage Users":
        if st.session_state.role == "admin":
            st.header("👑 Manage Users")
            c.execute("SELECT username, role FROM users")
            users = c.fetchall()
            for u in users:
                st.write(f"👤 {u[0]} ({u[1]})")
                if u[0] != "admin":
                    if st.button(f"Delete {u[0]}", key=f"usr_{u[0]}"):
                        delete_user(u[0])
                        st.success(f"User {u[0]} deleted.")
                        st.rerun()
        else:
            st.warning("Only admin can access this page.")

    elif menu == "Logout":
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.role = None
        st.rerun()

st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; font-weight:bold; color:#8B0000;'>Developed By:- Mool Chandra Vishwakarma</p>", unsafe_allow_html=True)
