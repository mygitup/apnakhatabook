import streamlit as st
import sqlite3
from datetime import datetime
import pandas as pd
import hashlib

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
# Helper: Password Hashing
# -----------------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# -----------------------------
# Default Admin Account (Auto Fix)
# -----------------------------
def ensure_admin():
    c.execute("SELECT username, password FROM users WHERE username='admin'")
    admin = c.fetchone()
    if not admin:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                  ("admin", hash_password("vinsolit"), "admin"))
        conn.commit()
    else:
        if admin[1] == "vinsolit":
            c.execute("UPDATE users SET password=? WHERE username='admin'",
                      (hash_password("vinsolit"),))
            conn.commit()
ensure_admin()


# -----------------------------
# Helper Functions
# -----------------------------
def add_user(username, password):
    try:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                  (username, hash_password(password), "user"))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def verify_user(username, password):
    c.execute("SELECT * FROM users WHERE username=? AND password=?",
              (username, hash_password(password)))
    return c.fetchone()


def get_records(owner):
    c.execute("SELECT * FROM records WHERE owner_username=?", (owner,))
    return c.fetchall()


# Modify update_record to accept optional datetime
def update_record(owner, received, paid_out, payee, note="", record_datetime=None):
    now = record_datetime.strftime("%Y-%m-%d %H:%M:%S") if record_datetime else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    c.execute("SELECT * FROM records WHERE owner_username=? AND payee=? ORDER BY id DESC LIMIT 1",
              (owner, payee))
    last_record = c.fetchone()
    prev_total_received = last_record[7] if last_record else 0
    prev_total_paid = last_record[6] if last_record else 0

    new_total_received = prev_total_received + received - paid_out
    if new_total_received < 0:
        new_total_received = 0
    new_total_paid = prev_total_paid + paid_out

    c.execute('''INSERT INTO records 
                 (owner_username, received, paid_out, datetime, payee, total_paid, total_received, note)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (owner, received, paid_out, now, payee, new_total_paid, new_total_received, note))
    conn.commit()


def delete_record_by_id(record_id):
    c.execute("DELETE FROM records WHERE id=?", (record_id,))
    conn.commit()


def delete_all_by_payee(owner, payee):
    c.execute("DELETE FROM records WHERE owner_username=? AND payee=?", (owner, payee))
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
# CSV Generator
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

st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #F0B2B1,#ABEDD5, #C7E663); font-family: 'Arial Black', sans-serif; }
    .title {text-align:center; font-size:45px;}
    .sub {text-align:center; font-size:20px;}
    .green-bold {color:#006400; background-color:#E0FFE0; padding:2px 5px; border-radius:5px;}
    .red-bold {color:#8B0000; background-color:#FFE0E0; padding:2px 5px; border-radius:5px;}
    .developer-sign {position: fixed; top: 10px; right: 20px; color:black; font-weight:bold;}
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='title'>💰 LenDenWebApp</div>", unsafe_allow_html=True)
st.markdown("<div class='sub'>Simple and Secure Record Management</div>", unsafe_allow_html=True)
st.markdown("<div class='developer-sign'>Developed By: Mool Chandra Vishwakarma</div>", unsafe_allow_html=True)
st.write("---")


# -----------------------------
# Auth Section
# -----------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.show_reset = False
    st.session_state.reset_user = None

if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Signup"])

    # -----------------------------
    # Login + Reset Password Tab
    # -----------------------------
    with tab1:
        u = st.text_input("Username", key="login_username")
        p = st.text_input("Password", type="password", key="login_password")

        if st.button("Login"):
            user = verify_user(u, p)
            if user:
                st.session_state.logged_in = True
                st.session_state.username = user[0]
                st.session_state.role = user[2]
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid credentials")

        # Reset Password Button
        if st.button("Reset Password"):
            if not u.strip():
                st.warning("Enter your username first to reset password.")
            else:
                st.session_state.reset_user = u.strip()
                st.session_state.show_reset = True

        # Show Reset Password Input if requested
        if st.session_state.show_reset and st.session_state.reset_user:
            new_pass = st.text_input("Enter New Password", type="password", key="new_pass_input")
            if st.button("Set New Password"):
                if not new_pass.strip():
                    st.warning("Password cannot be empty.")
                else:
                    c.execute("UPDATE users SET password=? WHERE username=?",
                              (hash_password(new_pass.strip()), st.session_state.reset_user))
                    conn.commit()
                    st.success(f"✅ Password for '{st.session_state.reset_user}' reset successfully!")
                    st.session_state.show_reset = False
                    st.session_state.reset_user = None

    # -----------------------------
    # Signup Tab
    # -----------------------------
    with tab2:
        nu = st.text_input("New Username", key="signup_username")
        np = st.text_input("New Password", type="password", key="signup_password")
        if st.button("Signup"):
            if add_user(nu, np):
                st.success("🎉 Account created!")
            else:
                st.error("Username already exists")

# -----------------------------
# Main App after Login
# -----------------------------
else:
    st.sidebar.title("Menu")
    st.sidebar.write(f"👤 `{st.session_state.username}` ({st.session_state.role})")
    menu = st.sidebar.radio("Navigate", ["My Record", "All Records", "Manage Users", "Logout"])

    if menu == "My Record":
        st.header("💼 My Record")

        c.execute("SELECT SUM(received), SUM(paid_out) FROM records WHERE owner_username=?", 
                  (st.session_state.username,))
        rec = c.fetchone()
        net_balance = (rec[0] or 0) - (rec[1] or 0)
        st.metric("💰 Net Balance", f"Rs.{net_balance:.2f}")

        user_records = get_records(st.session_state.username)

        search_term = st.text_input("Search Payee")
        if search_term:
            user_records = [r for r in user_records if search_term.lower() in r[5].lower()]

        if user_records:
            payees_seen = set()
            for rec in user_records:
                if rec[5] in payees_seen:
                    continue
                payees_seen.add(rec[5])
                c.execute("SELECT SUM(received), SUM(paid_out), MAX(datetime) FROM records WHERE owner_username=? AND payee=? ORDER BY id DESC",
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
                            col1, col2 = st.columns([4, 1])
                            with col1:
                                st.write(f"Received: Rs.{h[1]:.2f}, Paid: Rs.{h[2]:.2f}, Note: {h[4]}, Date: {h[3]}")
                            with col2:
                                confirm_key = f"chk_{h[0]}"
                                delete_key = f"del_{h[0]}"
                                checked = st.checkbox("Confirm delete", key=confirm_key)
                                if checked:
                                    if st.button("🗑 Delete", key=delete_key):
                                        delete_record_by_id(h[0])
                                        st.success("Deleted this record.")
                                        st.rerun()

                        warning_text = "⚠️ Optional: Delete entire payee history (only this payee)."
                        st.warning(warning_text)
                        chkall_key = f"chkall_{rec[5]}_{st.session_state.username}"
                        delall_key = f"delall_{rec[5]}_{st.session_state.username}"
                        checked_all = st.checkbox(f"Confirm delete all for {rec[5]}", key=chkall_key)
                        if checked_all:
                            if st.button(f"🗑 Delete All for {rec[5]}", key=delall_key):
                                delete_all_by_payee(st.session_state.username, rec[5])
                                st.success(f"All records for {rec[5]} deleted.")
                                st.rerun()

        csv_data = generate_csv(st.session_state.username)
        st.download_button("📄 Download All Records (CSV)", csv_data, file_name="All_Records.csv", mime="text/csv")

        with st.form("update_record_form"):
            received = st.number_input("Add Received Amount", min_value=0.0, step=0.01)
            paid_out = st.number_input("Add Paid Out Amount", min_value=0.0, step=0.01)
            payee = st.text_input("Payee Name")
            note = st.text_input("Note (optional)")

            from datetime import datetime as dt
            import datetime as datetime_module

            col1, col2 = st.columns(2)
            with col1:
                date_input = st.date_input("Date (optional)", dt.now().date())
            with col2:
                time_input = st.time_input("Time (optional)", dt.now().time())
            custom_datetime = datetime_module.datetime.combine(date_input, time_input)

            submitted = st.form_submit_button("Update Record")
            if submitted:
                if not payee.strip():
                    st.warning("Enter payee name.")
                else:
                    update_record(st.session_state.username, received, paid_out, payee.strip(), note, custom_datetime)
                    st.success("✅ Record added!")
                    st.rerun()

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
