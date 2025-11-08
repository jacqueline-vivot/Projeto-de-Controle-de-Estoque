import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv, datetime, os, sys

DB_FILE = "inventory.db"

# Optional libs
HAS_MPL = True
try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
except Exception:
    HAS_MPL = False

HAS_TKCAL = True
try:
    from tkcalendar import DateEntry
except Exception:
    HAS_TKCAL = False


# Banco de dados

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        quantity INTEGER DEFAULT 0,
        price REAL DEFAULT 0,
        expiry_date TEXT,
        created_at TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        created_at TEXT,
        note TEXT,
        FOREIGN KEY(product_id) REFERENCES products(id)
    )
    """)
    conn.commit()
    conn.close()

# Operações DB

def add_product(name, quantity, price, expiry_date):
    now = datetime.datetime.now().isoformat()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""INSERT INTO products (name,quantity,price,expiry_date,created_at)
                   VALUES (?,?,?,?,?)""", (name, quantity, price, expiry_date, now))
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return pid

def update_product(pid, name, quantity, price, expiry_date):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""UPDATE products SET name=?, quantity=?, price=?, expiry_date=? WHERE id=?""",
                (name, quantity, price, expiry_date, pid))
    conn.commit()
    conn.close()

def delete_product(pid):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM transactions WHERE product_id=?", (pid,))
    cur.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    conn.close()

def get_products(search=None):
    conn = get_connection()
    cur = conn.cursor()
    if search:
        s = f"%{search}%"
        cur.execute("SELECT * FROM products WHERE name LIKE ? ORDER BY name", (s,))
    else:
        cur.execute("SELECT * FROM products ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_product(pid):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE id=?", (pid,))
    row = cur.fetchone()
    conn.close()
    return row

def change_stock(pid, amount, ttype, note=""):
    prod = get_product(pid)
    if not prod:
        raise ValueError("Produto não encontrado.")
    new_q = prod["quantity"] + (amount if ttype == "in" else -amount)
    if new_q < 0:
        raise ValueError("Quantidade insuficiente.")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE products SET quantity=? WHERE id=?", (new_q, pid))
    now = datetime.datetime.now().isoformat()
    cur.execute("INSERT INTO transactions (product_id,type,quantity,created_at,note) VALUES (?,?,?,?,?)",
                (pid, ttype, amount, now, note))
    conn.commit()
    conn.close()

def get_transactions(product_id=None, limit=None):
    conn = get_connection()
    cur = conn.cursor()
    if product_id:
        cur.execute("""SELECT t.*, p.name FROM transactions t
                       JOIN products p ON p.id = t.product_id
                       WHERE product_id=?
                       ORDER BY created_at DESC""", (product_id,))
    else:
        cur.execute("""SELECT t.*, p.name FROM transactions t
                       JOIN products p ON p.id = t.product_id
                       ORDER BY created_at DESC""")
    rows = cur.fetchall()
    conn.close()
    if limit:
        return rows[:limit]
    return rows


# Utilitários

def safe_float(v, default=0.0):
    try:
        return float(v)
    except:
        return default

def safe_int(v, default=0):
    try:
        return int(v)
    except:
        return default

def parse_date_str(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        d = datetime.date.fromisoformat(s)
        return d.isoformat()
    except:
        return None


# Aplicação (UI)

class InventoryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Controle de Estoque")
        self.root.geometry("1000x640")
        self._create_styles()
        self._create_header()
        self._create_notebook()
        self._create_statusbar()
        self.refresh_all()

    def _create_styles(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except:
            pass
        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"), background="#2b6ea3", foreground="white")
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(10,6))
        style.configure("Treeview", rowheight=24, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

    def _create_header(self):
        header = ttk.Frame(self.root)
        header.pack(fill="x")
        lbl = tk.Label(header, text="  📦  Sistema de Controle de Estoque", bg="#2b6ea3", fg="white",
                       font=("Segoe UI", 12, "bold"), anchor="w")
        lbl.pack(fill="x")
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill="x", pady=6, padx=6)
        ttk.Button(toolbar, text="Atualizar", command=self.refresh_all).pack(side="left")
        ttk.Button(toolbar, text="Exportar Produtos CSV", command=self.export_products_csv).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Exportar Histórico CSV", command=self.export_transactions_csv).pack(side="left", padx=6)
        if HAS_MPL:
            ttk.Button(toolbar, text="Atualizar Gráfico", command=self.update_report_chart).pack(side="left", padx=6)
        else:
            ttk.Button(toolbar, text="Gráficos (instalar matplotlib)", command=self._inform_mpl).pack(side="left", padx=6)

    def _create_notebook(self):
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=10, pady=(0,10))

        self.tab_dashboard = ttk.Frame(self.nb)
        self.nb.add(self.tab_dashboard, text="Resumo")

        self.tab_inventory = ttk.Frame(self.nb)
        self.nb.add(self.tab_inventory, text="Estoque")

        self.tab_transactions = ttk.Frame(self.nb)
        self.nb.add(self.tab_transactions, text="Movimentações")

        self.tab_reports = ttk.Frame(self.nb)
        self.nb.add(self.tab_reports, text="Relatórios")

        self._build_dashboard()
        self._build_inventory()
        self._build_transactions()
        self._build_reports()

    def _create_statusbar(self):
        self.status_var = tk.StringVar(value="Pronto")
        status = ttk.Frame(self.root)
        status.pack(fill="x", side="bottom")
        ttk.Label(status, textvariable=self.status_var).pack(side="left", padx=6, pady=4)

    #Dashboard
    def _build_dashboard(self):
        frame = ttk.Frame(self.tab_dashboard, padding=10)
        frame.pack(fill="both", expand=True)
        top = ttk.Frame(frame)
        top.pack(fill="x")
        self.card_total = self._card(top, "Total de Produtos", "0")
        self.card_units = self._card(top, "Unidades em Estoque", "0")
        self.card_low = self._card(top, "Produtos com Estoque Baixo", "0")
        for c in (self.card_total, self.card_units, self.card_low):
            c.pack(side="left", padx=6, expand=True, fill="x")

        bottom = ttk.Frame(frame)
        bottom.pack(fill="both", expand=True, pady=(12,0))
        left = ttk.Frame(bottom)
        left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="Entradas/Saídas recentes", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.rv_recent = ttk.Treeview(left, columns=("prod","type","qty","date"), show="headings", height=12)
        for c,t in [("prod","Produto"),("type","Tipo"),("qty","Qtd"),("date","Data")]:
            self.rv_recent.heading(c, text=t)
            self.rv_recent.column(c, anchor="center")
        self.rv_recent.pack(fill="both", expand=True, pady=6)

        right = ttk.Frame(bottom, width=260)
        right.pack(side="left", fill="y")
        ttk.Label(right, text="Produtos com estoque baixo", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.lv_low = ttk.Treeview(right, columns=("name","qty"), show="headings", height=12)
        self.lv_low.heading("name", text="Produto")
        self.lv_low.heading("qty", text="Qtd")
        self.lv_low.pack(fill="both", expand=True, pady=6)

    def _card(self, parent, title, value):
        f = ttk.Frame(parent, padding=10, relief="raised")
        ttk.Label(f, text=title).pack(anchor="w")
        lbl = ttk.Label(f, text=value, font=("Segoe UI", 16, "bold"))
        lbl.pack(anchor="w", pady=(6,0))
        f.value_label = lbl
        return f

    #Inventory
    def _build_inventory(self):
        container = ttk.Frame(self.tab_inventory, padding=10)
        container.pack(fill="both", expand=True)
        top = ttk.Frame(container)
        top.pack(fill="x")
        ttk.Label(top, text="Pesquisar:").pack(side="left")
        self.inv_search = tk.StringVar()
        ttk.Entry(top, textvariable=self.inv_search).pack(side="left", padx=6)
        ttk.Button(top, text="Pesquisar", command=self.refresh_inventory).pack(side="left")
        ttk.Button(top, text="Novo Produto", command=self.open_add_product).pack(side="left", padx=6)

        self.tree_inv = ttk.Treeview(container, columns=("id","name","qty","price","expiry"), show="headings")
        self.tree_inv.heading("id", text="ID"); self.tree_inv.column("id", width=60, anchor="center")
        self.tree_inv.heading("name", text="Nome"); self.tree_inv.column("name", width=380)
        self.tree_inv.heading("qty", text="Qtd"); self.tree_inv.column("qty", width=80, anchor="center")
        self.tree_inv.heading("price", text="Preço (R$)"); self.tree_inv.column("price", width=120, anchor="center")
        self.tree_inv.heading("expiry", text="Validade"); self.tree_inv.column("expiry", width=120, anchor="center")
        self.tree_inv.pack(fill="both", expand=True, pady=8)

        footer = ttk.Frame(container)
        footer.pack(fill="x")
        ttk.Button(footer, text="Editar", command=self.open_edit_selected).pack(side="left", padx=4)
        ttk.Button(footer, text="Entrada", command=lambda: self.open_stock("in")).pack(side="left", padx=4)
        ttk.Button(footer, text="Saída", command=lambda: self.open_stock("out")).pack(side="left", padx=4)
        ttk.Button(footer, text="Excluir", command=self.delete_selected).pack(side="left", padx=4)
        ttk.Button(footer, text="Exportar CSV", command=self.export_products_csv).pack(side="right")

    #Transactions
    def _build_transactions(self):
        container = ttk.Frame(self.tab_transactions, padding=10)
        container.pack(fill="both", expand=True)
        top = ttk.Frame(container)
        top.pack(fill="x")
        ttk.Button(top, text="Atualizar", command=self.refresh_transactions).pack(side="left")
        ttk.Button(top, text="Exportar CSV", command=self.export_transactions_csv).pack(side="left", padx=6)

        self.tree_tr = ttk.Treeview(container, columns=("prod","type","qty","date","note"), show="headings")
        self.tree_tr.heading("prod", text="Produto")
        self.tree_tr.heading("type", text="Tipo")
        self.tree_tr.heading("qty", text="Qtd")
        self.tree_tr.heading("date", text="Data")
        self.tree_tr.heading("note", text="Observação")
        self.tree_tr.pack(fill="both", expand=True, pady=8)

    #Reports
    def _build_reports(self):
        container = ttk.Frame(self.tab_reports, padding=10)
        container.pack(fill="both", expand=True)
        top = ttk.Frame(container)
        top.pack(fill="x")
        ttk.Label(top, text="Período (dias):").pack(side="left")
        self.report_days = tk.IntVar(value=30)
        ttk.Entry(top, textvariable=self.report_days, width=6).pack(side="left", padx=6)
        ttk.Button(top, text="Gerar Relatório", command=self.update_report_chart).pack(side="left")
        if not HAS_MPL:
            ttk.Label(container, text="matplotlib não instalado. Instale com: pip install matplotlib", foreground="gray").pack(pady=12)
            return

        self.fig = plt.Figure(figsize=(8,4))
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=container)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.report_table = ttk.Treeview(container, columns=("date","in","out"), show="headings", height=6)
        self.report_table.heading("date", text="Data")
        self.report_table.heading("in", text="Entradas")
        self.report_table.heading("out", text="Saídas")
        self.report_table.pack(fill="x", pady=8)

    #Actions / Refresh
    def refresh_all(self):
        self.refresh_dashboard()
        self.refresh_inventory()
        self.refresh_transactions()
        self.update_report_chart()

    def refresh_dashboard(self):
        prods = get_products()
        total_products = len(prods)
        total_units = sum([p["quantity"] for p in prods])
        low = [p for p in prods if p["quantity"] <= 5]
        self.card_total.value_label.config(text=str(total_products))
        self.card_units.value_label.config(text=str(total_units))
        self.card_low.value_label.config(text=str(len(low)))

        for i in self.rv_recent.get_children(): self.rv_recent.delete(i)
        recent = get_transactions(limit=10)
        for r in recent:
            tipo = "Entrada" if r["type"] == "in" else "Saída"
            self.rv_recent.insert("", "end", values=(r["name"], tipo, r["quantity"], r["created_at"][:19]))

        for i in self.lv_low.get_children(): self.lv_low.delete(i)
        for p in low[:12]:
            self.lv_low.insert("", "end", values=(p["name"], p["quantity"]))

    def refresh_inventory(self):
        s = self.inv_search.get().strip()
        rows = get_products(s if s else None)
        for i in self.tree_inv.get_children(): self.tree_inv.delete(i)
        for r in rows:
            exp = r["expiry_date"] or "-"
            self.tree_inv.insert("", "end", iid=r["id"], values=(r["id"], r["name"], r["quantity"], f"{r['price']:.2f}", exp))

    def refresh_transactions(self):
        for i in self.tree_tr.get_children(): self.tree_tr.delete(i)
        rows = get_transactions()
        for r in rows:
            tipo = "Entrada" if r["type"] == "in" else "Saída"
            self.tree_tr.insert("", "end", values=(r["name"], tipo, r["quantity"], r["created_at"][:19], r["note"] or ""))

    def get_selected_inventory_id(self):
        sel = self.tree_inv.selection()
        if not sel:
            messagebox.showinfo("Selecionar", "Selecione um produto.")
            return None
        return int(sel[0])

    def open_add_product(self):
        dlg = ProductDialog(self.root, title="Novo Produto")
        self.root.wait_window(dlg)
        if getattr(dlg, "saved", False):
            name, qty, price, expiry = dlg.result
            add_product(name, qty, price, expiry)
            self.refresh_inventory()
            self.refresh_dashboard()

    def open_edit_selected(self):
        pid = self.get_selected_inventory_id()
        if not pid: return
        prod = get_product(pid)
        dlg = ProductDialog(self.root, product=prod, title="Editar Produto")
        self.root.wait_window(dlg)
        if getattr(dlg, "saved", False):
            name, qty, price, expiry = dlg.result
            update_product(pid, name, qty, price, expiry)
            self.refresh_inventory()
            self.refresh_dashboard()

    def delete_selected(self):
        pid = self.get_selected_inventory_id()
        if not pid: return
        p = get_product(pid)
        if messagebox.askyesno("Confirmar", f"Excluir '{p['name']}' e histórico?"):
            delete_product(pid)
            self.refresh_inventory()
            self.refresh_dashboard()

    def open_stock(self, ttype):
        pid = self.get_selected_inventory_id()
        if not pid: return
        prod = get_product(pid)
        dlg = StockDialog(self.root, product=prod, ttype=ttype)
        self.root.wait_window(dlg)
        if getattr(dlg, "applied", False):
            qty, note = dlg.result
            try:
                change_stock(pid, qty, ttype, note)
                messagebox.showinfo("Sucesso", "Movimentação registrada.")
                self.refresh_inventory()
                self.refresh_dashboard()
                self.refresh_transactions()
            except Exception as e:
                messagebox.showerror("Erro", str(e))

    #Reports
    def update_report_chart(self):
        if not HAS_MPL:
            return
        days = max(1, int(self.report_days.get() or 30))
        end = datetime.date.today()
        start = end - datetime.timedelta(days=days-1)
        dates = [(start + datetime.timedelta(days=i)).isoformat() for i in range(days)]
        in_map = {d:0 for d in dates}
        out_map = {d:0 for d in dates}
        rows = get_transactions()
        for r in rows:
            dt = r["created_at"][:10]
            if dt >= start.isoformat() and dt <= end.isoformat():
                if r["type"] == "in":
                    in_map[dt] += r["quantity"]
                else:
                    out_map[dt] += r["quantity"]
        x = [datetime.date.fromisoformat(d) for d in dates]
        y_in = [in_map[d] for d in dates]
        y_out = [out_map[d] for d in dates]
        self.ax.clear()
        self.ax.plot(x, y_in, label="Entradas")
        self.ax.plot(x, y_out, label="Saídas")
        self.ax.set_title(f"Entradas vs Saídas (últimos {days} dias)")
        self.ax.legend()
        self.ax.grid(True)
        self.fig.autofmt_xdate()
        self.canvas.draw()

        for i in self.report_table.get_children(): self.report_table.delete(i)
        for d in dates:
            self.report_table.insert("", "end", values=(d, in_map[d], out_map[d]))

    def _inform_mpl(self):
        messagebox.showinfo("matplotlib ausente", "Instale matplotlib para habilitar gráficos:\n\npip install matplotlib")

    # ---------------- Export ----------------
    def export_products_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
        if not path: return
        rows = get_products()
        with open(path, "w", newline='', encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id","name","quantity","price","expiry_date","created_at"])
            for r in rows:
                w.writerow([r["id"], r["name"], r["quantity"], r["price"], r["expiry_date"], r["created_at"]])
        messagebox.showinfo("Exportado", f"Produtos exportados para {os.path.basename(path)}")

    def export_transactions_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
        if not path: return
        rows = get_transactions()
        with open(path, "w", newline='', encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id","product_id","product_name","type","quantity","created_at","note"])
            for r in rows:
                w.writerow([r["id"], r["product_id"], r["name"], r["type"], r["quantity"], r["created_at"], r["note"]])
        messagebox.showinfo("Exportado", f"Histórico exportado para {os.path.basename(path)}")

#Dialogs 
class ProductDialog(tk.Toplevel):
    def __init__(self, parent, product=None, title="Produto"):
        super().__init__(parent)
        self.product = product
        self.result = None
        self.saved = False
        self.title(title)
        self.geometry("420x340")
        self.configure(padx=12, pady=12)
        self._build()
        if product:
            self._load(product)

    def _build(self):
        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Nome:").grid(row=0, column=0, sticky="w", pady=6)
        self.e_name = ttk.Entry(frm, width=40)
        self.e_name.grid(row=0, column=1, pady=6)
        ttk.Label(frm, text="Quantidade:").grid(row=1, column=0, sticky="w", pady=6)
        self.e_qty = ttk.Entry(frm, width=12)
        self.e_qty.grid(row=1, column=1, sticky="w", pady=6)
        ttk.Label(frm, text="Preço (R$):").grid(row=2, column=0, sticky="w", pady=6)
        self.e_price = ttk.Entry(frm, width=12)
        self.e_price.grid(row=2, column=1, sticky="w", pady=6)
        ttk.Label(frm, text="Data de validade (YYYY-MM-DD):").grid(row=3, column=0, sticky="w", pady=6)

        # If tkcalendar is present, use DateEntry; else use simple Entry
        if HAS_TKCAL:
            self.e_expiry = DateEntry(frm, date_pattern="yyyy-mm-dd")
            self.e_expiry.grid(row=3, column=1, sticky="w", pady=6)
        else:
            self.e_expiry = ttk.Entry(frm, width=18)
            self.e_expiry.grid(row=3, column=1, sticky="w", pady=6)
            ttk.Label(frm, text="(Instale tkcalendar para um seletor de datas)").grid(row=4, column=1, sticky="w")

        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, columnspan=2, pady=12)
        ttk.Button(btns, text="Salvar", command=self._on_save).pack(side="left", padx=6)
        ttk.Button(btns, text="Cancelar", command=self.destroy).pack(side="left", padx=6)

    def _load(self, p):
        self.e_name.insert(0, p["name"])
        self.e_qty.insert(0, str(p["quantity"]))
        self.e_price.insert(0, f"{p['price']:.2f}")
        if p["expiry_date"]:
            # if DateEntry, set via set_date if available
            try:
                if HAS_TKCAL and hasattr(self.e_expiry, "set_date"):
                    self.e_expiry.set_date(p["expiry_date"])
                else:
                    self.e_expiry.insert(0, p["expiry_date"])
            except:
                self.e_expiry.insert(0, p["expiry_date"])

    def _on_save(self):
        name = self.e_name.get().strip()
        qty = safe_int(self.e_qty.get().strip(), 0)
        price = safe_float(self.e_price.get().strip(), 0.0)
        # read expiry depending on widget
        expiry = None
        if HAS_TKCAL and hasattr(self.e_expiry, "get_date"):
            try:
                d = self.e_expiry.get_date()
                expiry = d.isoformat()
            except:
                expiry = None
        else:
            expiry = parse_date_str(self.e_expiry.get().strip())

        if not name:
            messagebox.showerror("Erro", "Nome é obrigatório.")
            return
        self.result = (name, qty, price, expiry)
        self.saved = True
        self.destroy()

class StockDialog(tk.Toplevel):
    def __init__(self, parent, product, ttype):
        super().__init__(parent)
        self.product = product
        self.ttype = ttype
        self.result = None
        self.applied = False
        self.title(f"{'Entrada' if ttype=='in' else 'Saída'} - {product['name']}")
        self.geometry("360x240")
        self.configure(padx=12, pady=12)
        self._build()

    def _build(self):
        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"Produto: {self.product['name']}", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(frm, text=f"Estoque atual: {self.product['quantity']}").pack(anchor="w", pady=(4,8))
        ttk.Label(frm, text="Quantidade:").pack(anchor="w")
        self.e_qty = ttk.Entry(frm, width=12)
        self.e_qty.insert(0, "1")
        self.e_qty.pack(anchor="w", pady=4)
        ttk.Label(frm, text="Observação (opcional):").pack(anchor="w")
        self.tx_note = tk.Text(frm, height=4, width=38)
        self.tx_note.pack()
        btns = ttk.Frame(frm)
        btns.pack(pady=8)
        ttk.Button(btns, text="Aplicar", command=self._apply).pack(side="left", padx=6)
        ttk.Button(btns, text="Cancelar", command=self.destroy).pack(side="left", padx=6)

    def _apply(self):
        qty = safe_int(self.e_qty.get().strip(), 0)
        if qty <= 0:
            messagebox.showerror("Erro", "Quantidade deve ser positiva.")
            return
        note = self.tx_note.get("1.0", "end").strip()
        self.result = (qty, note)
        self.applied = True
        self.destroy()


# Main

def main():
    init_db()
    root = tk.Tk()
    app = InventoryApp(root)
    # If matplotlib is available, initialize report axes
    if HAS_MPL:
        # create axes placeholders so update_report_chart won't break if invoked early
        app.ax = app.fig.add_subplot(111) if hasattr(app, 'fig') else None
    root.mainloop()

if __name__ == "__main__":
    main()
