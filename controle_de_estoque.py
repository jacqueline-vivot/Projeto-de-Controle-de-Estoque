import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import csv, datetime, os

DB_FILE = "inventory.db"


# Banco de Dados

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
        code TEXT UNIQUE,
        name TEXT NOT NULL,
        description TEXT,
        price REAL DEFAULT 0,
        quantity INTEGER DEFAULT 0,
        created_at TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        note TEXT,
        created_at TEXT,
        FOREIGN KEY(product_id) REFERENCES products(id)
    )
    """)
    conn.commit()
    conn.close()


# Operações de BD

def add_product(code, name, description, price, quantity):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.datetime.now().isoformat()
    try:
        cur.execute("INSERT INTO products (code,name,description,price,quantity,created_at) VALUES (?,?,?,?,?,?)",
                    (code, name, description, price, quantity, now))
        conn.commit()
    except sqlite3.IntegrityError:
        messagebox.showerror("Erro", "Código já existente.")
    finally:
        conn.close()

def update_product(pid, code, name, description, price, quantity):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""UPDATE products SET code=?, name=?, description=?, price=?, quantity=? WHERE id=?""",
                (code, name, description, price, quantity, pid))
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
        like = f"%{search}%"
        cur.execute("SELECT * FROM products WHERE code LIKE ? OR name LIKE ? ORDER BY name", (like, like))
    else:
        cur.execute("SELECT * FROM products ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_product_by_id(pid):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE id=?", (pid,))
    row = cur.fetchone()
    conn.close()
    return row

def change_stock(pid, amount, ttype, note=""):
    conn = get_connection()
    cur = conn.cursor()
    prod = get_product_by_id(pid)
    if not prod:
        raise ValueError("Produto não encontrado.")
    new_qty = prod["quantity"] + (amount if ttype == "in" else -amount)
    if new_qty < 0:
        raise ValueError("Quantidade insuficiente no estoque.")
    cur.execute("UPDATE products SET quantity=? WHERE id=?", (new_qty, pid))
    now = datetime.datetime.now().isoformat()
    cur.execute("INSERT INTO transactions (product_id,type,quantity,note,created_at) VALUES (?,?,?,?,?)",
                (pid, ttype, amount, note, now))
    conn.commit()
    conn.close()

def get_transactions(product_id=None):
    conn = get_connection()
    cur = conn.cursor()
    if product_id:
        cur.execute("""SELECT t.*, p.code, p.name FROM transactions t
                       JOIN products p ON p.id = t.product_id
                       WHERE product_id=?
                       ORDER BY created_at DESC""", (product_id,))
    else:
        cur.execute("""SELECT t.*, p.code, p.name FROM transactions t
                       JOIN products p ON p.id = t.product_id
                       ORDER BY created_at DESC""")
    rows = cur.fetchall()
    conn.close()
    return rows


# Interface Gráfica

class InventoryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Controle de Estoque Moderno")
        self.root.geometry("950x550")
        self.root.configure(bg="#eef2f5")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview.Heading", background="#d0e1f9", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=25, font=("Segoe UI", 10))
        style.configure("TButton", padding=6, relief="flat", background="#3f72af", foreground="white")
        style.map("TButton", background=[("active", "#2a4d8a")])

        title = tk.Label(self.root, text="📦 Sistema de Controle de Estoque", bg="#3f72af", fg="white",
                         font=("Segoe UI Semibold", 14), pady=8)
        title.pack(fill="x")

        self.create_topbar()
        self.create_table()
        self.create_footer()
        self.refresh_products()

    def create_topbar(self):
        frame = ttk.Frame(self.root, padding=8)
        frame.pack(fill="x")
        ttk.Label(frame, text="Buscar produto:").pack(side="left")
        self.search_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.search_var, width=30).pack(side="left", padx=6)
        ttk.Button(frame, text="Pesquisar", command=self.refresh_products).pack(side="left")
        ttk.Button(frame, text="Adicionar Produto", command=self.open_add_product).pack(side="left", padx=4)
        ttk.Button(frame, text="Exportar CSV", command=self.export_products_csv).pack(side="left", padx=4)

    def create_table(self):
        frame = ttk.Frame(self.root, padding=8)
        frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(frame, columns=("code","name","price","quantity"), show="headings")
        self.tree.heading("code", text="Código")
        self.tree.heading("name", text="Nome")
        self.tree.heading("price", text="Preço (R$)")
        self.tree.heading("quantity", text="Estoque")
        self.tree.column("code", width=100, anchor="center")
        self.tree.column("name", width=250)
        self.tree.column("price", width=100, anchor="center")
        self.tree.column("quantity", width=100, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<Double-1>", lambda e=None: self.open_product_detail())

    def create_footer(self):
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill="x")
        ttk.Button(frame, text="Editar", command=self.open_product_detail).pack(side="left", padx=4)
        ttk.Button(frame, text="Entrada", command=lambda: self.stock_action("in")).pack(side="left", padx=4)
        ttk.Button(frame, text="Saída", command=lambda: self.stock_action("out")).pack(side="left", padx=4)
        ttk.Button(frame, text="Histórico", command=self.open_transactions).pack(side="left", padx=4)
        ttk.Button(frame, text="Excluir", command=self.delete_selected).pack(side="left", padx=4)

    def refresh_products(self):
        search = self.search_var.get().strip()
        rows = get_products(search)
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in rows:
            self.tree.insert("", "end", iid=r["id"], values=(
                r["code"], r["name"], f"{r['price']:.2f}", r["quantity"]
            ))

    def get_selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Atenção", "Selecione um produto.")
            return None
        return int(sel[0])

    def open_add_product(self):
        ProductDialog(self.root, on_save=self.refresh_products)

    def open_product_detail(self):
        pid = self.get_selected_id()
        if not pid: return
        prod = get_product_by_id(pid)
        if prod:
            ProductDialog(self.root, product=prod, on_save=self.refresh_products)

    def stock_action(self, ttype):
        pid = self.get_selected_id()
        if not pid: return
        prod = get_product_by_id(pid)
        StockDialog(self.root, product=prod, ttype=ttype, on_save=lambda q, n: self.apply_stock(pid, q, ttype, n))

    def apply_stock(self, pid, qty, ttype, note):
        try:
            qty = int(qty)
            change_stock(pid, qty, ttype, note)
            messagebox.showinfo("Sucesso", "Movimentação registrada.")
            self.refresh_products()
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def open_transactions(self):
        TransactionsWindow(self.root)

    def delete_selected(self):
        pid = self.get_selected_id()
        if not pid: return
        prod = get_product_by_id(pid)
        if messagebox.askyesno("Confirmar", f"Excluir {prod['name']}?"):
            delete_product(pid)
            self.refresh_products()

    def export_products_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", title="Salvar como...", filetypes=[("CSV","*.csv")])
        if not path: return
        rows = get_products()
        with open(path, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Código", "Nome", "Descrição", "Preço", "Quantidade"])
            for r in rows:
                writer.writerow([r["code"], r["name"], r["description"], r["price"], r["quantity"]])
        messagebox.showinfo("Exportado", f"Arquivo salvo em {os.path.basename(path)}")


# Dialogs

class ProductDialog(tk.Toplevel):
    def __init__(self, parent, product=None, on_save=None):
        super().__init__(parent)
        self.product = product
        self.on_save = on_save
        self.title("Editar Produto" if product else "Novo Produto")
        self.geometry("400x380")
        self.configure(bg="#f8f9fa")
        self.create_widgets()
        if product: self.load_data()

    def create_widgets(self):
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Código:").grid(row=0, column=0, sticky="w")
        self.code = ttk.Entry(frm, width=30)
        self.code.grid(row=0, column=1, pady=3)
        ttk.Label(frm, text="Nome:").grid(row=1, column=0, sticky="w")
        self.name = ttk.Entry(frm, width=30)
        self.name.grid(row=1, column=1, pady=3)
        ttk.Label(frm, text="Descrição:").grid(row=2, column=0, sticky="nw")
        self.desc = tk.Text(frm, width=30, height=4)
        self.desc.grid(row=2, column=1, pady=3)
        ttk.Label(frm, text="Preço:").grid(row=3, column=0, sticky="w")
        self.price = ttk.Entry(frm, width=15)
        self.price.grid(row=3, column=1, sticky="w", pady=3)
        ttk.Label(frm, text="Quantidade:").grid(row=4, column=0, sticky="w")
        self.qty = ttk.Entry(frm, width=15)
        self.qty.grid(row=4, column=1, sticky="w", pady=3)

        ttk.Button(frm, text="Salvar", command=self.save).grid(row=5, column=1, sticky="e", pady=10)

    def load_data(self):
        self.code.insert(0, self.product["code"])
        self.name.insert(0, self.product["name"])
        self.desc.insert("1.0", self.product["description"] or "")
        self.price.insert(0, f"{self.product['price']:.2f}")
        self.qty.insert(0, str(self.product["quantity"]))

    def save(self):
        try:
            price = float(self.price.get().strip())
            qty = int(self.qty.get().strip())
        except:
            messagebox.showerror("Erro", "Valores inválidos.")
            return
        data = dict(code=self.code.get().strip(), name=self.name.get().strip(),
                    description=self.desc.get("1.0","end").strip(), price=price, quantity=qty)
        if not data["name"]:
            messagebox.showerror("Erro", "Nome obrigatório.")
            return
        if self.product:
            update_product(self.product["id"], **data)
        else:
            add_product(**data)
        if self.on_save:
            self.on_save()
        self.destroy()

class StockDialog(simpledialog.Dialog):
    def __init__(self, parent, product, ttype, on_save):
        self.product, self.ttype, self.on_save = product, ttype, on_save
        super().__init__(parent, title=f"{'Entrada' if ttype=='in' else 'Saída'} - {product['name']}")

    def body(self, master):
        ttk.Label(master, text=f"Produto: {self.product['name']}").pack(pady=5)
        ttk.Label(master, text=f"Estoque atual: {self.product['quantity']}").pack(pady=5)
        frm = ttk.Frame(master)
        frm.pack(pady=5)
        ttk.Label(frm, text="Quantidade:").grid(row=0, column=0)
        self.qty = ttk.Entry(frm)
        self.qty.grid(row=0, column=1)
        ttk.Label(frm, text="Observação:").grid(row=1, column=0, sticky="nw", pady=3)
        self.note = tk.Text(frm, width=30, height=3)
        self.note.grid(row=1, column=1)
        return self.qty

    def apply(self):
        qty = self.qty.get().strip()
        note = self.note.get("1.0","end").strip()
        if self.on_save:
            self.on_save(qty, note)

class TransactionsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Histórico de Movimentações")
        self.geometry("750x400")
        self.create_table()
        self.refresh()

    def create_table(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=("product","type","qty","note","date"), show="headings")
        for col, txt in zip(self.tree["columns"], ["Produto","Tipo","Qtd","Observação","Data"]):
            self.tree.heading(col, text=txt)
            self.tree.column(col, anchor="center")
        self.tree.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(frame, command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = get_transactions()
        for r in rows:
            tipo = "Entrada" if r["type"] == "in" else "Saída"
            self.tree.insert("", "end", values=(r["name"], tipo, r["quantity"], r["note"], r["created_at"]))


# Main

def main():
    init_db()
    root = tk.Tk()
    InventoryApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
