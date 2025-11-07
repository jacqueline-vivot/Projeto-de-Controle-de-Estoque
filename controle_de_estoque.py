import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import csv
import datetime
import os

DB_FILE = "inventory.db"


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
        type TEXT NOT NULL, -- 'in' or 'out'
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
        return cur.lastrowid
    except sqlite3.IntegrityError:
        messagebox.showerror("Erro", "Código já existe. Use outro código.")
        return None
    finally:
        conn.close()

def update_product(pid, code, name, description, price, quantity):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""UPDATE products SET code=?, name=?, description=?, price=?, quantity=? WHERE id=?""",
                    (code, name, description, price, quantity, pid))
        conn.commit()
    except sqlite3.IntegrityError:
        messagebox.showerror("Erro", "Código já existe. Use outro código.")
    finally:
        conn.close()

def delete_product(pid):
    conn = get_connection()
    cur = conn.cursor()
    # excluir transações relacionadas
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
    # ttype: 'in' or 'out'; amount positive integer
    conn = get_connection()
    cur = conn.cursor()
    prod = get_product_by_id(pid)
    if not prod:
        conn.close()
        raise ValueError("Produto não encontrado")
    new_qty = prod["quantity"] + (amount if ttype == "in" else -amount)
    if new_qty < 0:
        conn.close()
        raise ValueError("Quantidade insuficiente no estoque")
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


# GUI

class InventoryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Controle de Estoque")
        self.create_widgets()
        self.refresh_products()

    def create_widgets(self):
        # topo: busca e botões
        topframe = ttk.Frame(self.root, padding=8)
        topframe.pack(fill="x")

        ttk.Label(topframe, text="Buscar:").pack(side="left")
        self.search_var = tk.StringVar()
        e = ttk.Entry(topframe, textvariable=self.search_var)
        e.pack(side="left", padx=(4,8))
        e.bind("<Return>", lambda e=None: self.refresh_products())

        ttk.Button(topframe, text="Pesquisar", command=self.refresh_products).pack(side="left")
        ttk.Button(topframe, text="Adicionar Produto", command=self.open_add_product).pack(side="left", padx=6)
        ttk.Button(topframe, text="Exportar Produtos CSV", command=self.export_products_csv).pack(side="left", padx=6)

        # quadro principal: lista de produtos
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(main, columns=("code","name","price","quantity"), show="headings", selectmode="browse")
        self.tree.heading("code", text="Código")
        self.tree.heading("name", text="Nome")
        self.tree.heading("price", text="Preço")
        self.tree.heading("quantity", text="Quantidade")
        self.tree.column("code", width=100)
        self.tree.column("name", width=220)
        self.tree.column("price", width=80, anchor="e")
        self.tree.column("quantity", width=80, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.bind("<Double-1>", lambda e: self.open_product_detail())

        scrollbar = ttk.Scrollbar(main, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="left", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        # painel lateral de ações
        side = ttk.Frame(self.root, padding=8)
        side.pack(fill="x")

        ttk.Button(side, text="Detalhes / Editar", command=self.open_product_detail).pack(side="left", padx=4)
        ttk.Button(side, text="Entrada (In)", command=lambda: self.open_stock_dialog("in")).pack(side="left", padx=4)
        ttk.Button(side, text="Saída (Out)", command=lambda: self.open_stock_dialog("out")).pack(side="left", padx=4)
        ttk.Button(side, text="Excluir Produto", command=self.delete_selected_product).pack(side="left", padx=4)
        ttk.Button(side, text="Ver Histórico", command=self.open_transactions).pack(side="left", padx=4)
        ttk.Button(side, text="Exportar Histórico CSV", command=self.export_transactions_csv).pack(side="left", padx=4)

    def refresh_products(self):
        search = self.search_var.get().strip()
        rows = get_products(search if search else None)
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in rows:
            price_str = f"{r['price']:.2f}" if r['price'] is not None else "0.00"
            self.tree.insert("", "end", iid=r["id"], values=(r["code"], r["name"], price_str, r["quantity"]))

    def open_add_product(self):
        ProductDialog(self.root, on_save=self.on_product_added)

    def on_product_added(self, product):
        add_product(product['code'], product['name'], product['description'], product['price'], product['quantity'])
        self.refresh_products()

    def get_selected_product_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Selecionar", "Selecione um produto primeiro.")
            return None
        return int(sel[0])

    def open_product_detail(self):
        pid = self.get_selected_product_id()
        if not pid:
            return
        prod = get_product_by_id(pid)
        if not prod:
            messagebox.showerror("Erro", "Produto não encontrado.")
            return
        ProductDialog(self.root, product=prod, on_save=lambda p: self.save_product(pid, p))

    def save_product(self, pid, p):
        update_product(pid, p['code'], p['name'], p['description'], p['price'], p['quantity'])
        self.refresh_products()

    def delete_selected_product(self):
        pid = self.get_selected_product_id()
        if not pid:
            return
        prod = get_product_by_id(pid)
        if not prod:
            messagebox.showerror("Erro", "Produto não encontrado.")
            return
        if messagebox.askyesno("Confirmar", f"Excluir produto '{prod['name']}' e seu histórico?"):
            delete_product(pid)
            self.refresh_products()

    def open_stock_dialog(self, ttype):
        pid = self.get_selected_product_id()
        if not pid:
            return
        prod = get_product_by_id(pid)
        if not prod:
            messagebox.showerror("Erro", "Produto não encontrado.")
            return
        StockDialog(self.root, product=prod, ttype=ttype, on_save=lambda qty, note: self.apply_stock(pid, qty, ttype, note))

    def apply_stock(self, pid, qty, ttype, note):
        try:
            qty = int(qty)
            if qty <= 0:
                raise ValueError("Quantidade deve ser positiva.")
            change_stock(pid, qty, ttype, note)
            self.refresh_products()
            messagebox.showinfo("Sucesso", f"{'Entrada' if ttype=='in' else 'Saída'} registrada.")
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def open_transactions(self):
        pid = self.get_selected_product_id()
        TransactionsWindow(self.root, product_id=pid)

    def export_products_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files","*.csv")], title="Salvar produtos como...")
        if not path:
            return
        rows = get_products()
        with open(path, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id","code","name","description","price","quantity","created_at"])
            for r in rows:
                writer.writerow([r['id'], r['code'], r['name'], r['description'], r['price'], r['quantity'], r['created_at']])
        messagebox.showinfo("Exportado", f"Produtos exportados para {os.path.basename(path)}")

    def export_transactions_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files","*.csv")], title="Salvar histórico como...")
        if not path:
            return
        rows = get_transactions()
        with open(path, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id","product_id","product_code","product_name","type","quantity","note","created_at"])
            for r in rows:
                writer.writerow([r['id'], r['product_id'], r['code'], r['name'], r['type'], r['quantity'], r['note'], r['created_at']])
        messagebox.showinfo("Exportado", f"Histórico exportado para {os.path.basename(path)}")


# Dialogs

class ProductDialog(tk.Toplevel):
    def __init__(self, parent, product=None, on_save=None):
        super().__init__(parent)
        self.product = product
        self.on_save = on_save
        self.title("Produto" if product else "Adicionar Produto")
        self.resizable(False, False)
        self.create_widgets()
        if product:
            self.load_product()

    def create_widgets(self):
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Código:").grid(row=0, column=0, sticky="w")
        self.code_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.code_var).grid(row=0, column=1, sticky="ew")

        ttk.Label(frm, text="Nome:").grid(row=1, column=0, sticky="w")
        self.name_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.name_var).grid(row=1, column=1, sticky="ew")

        ttk.Label(frm, text="Descrição:").grid(row=2, column=0, sticky="nw")
        self.desc_text = tk.Text(frm, width=40, height=4)
        self.desc_text.grid(row=2, column=1, sticky="ew")

        ttk.Label(frm, text="Preço:").grid(row=3, column=0, sticky="w")
        self.price_var = tk.StringVar(value="0.00")
        ttk.Entry(frm, textvariable=self.price_var).grid(row=3, column=1, sticky="ew")

        ttk.Label(frm, text="Quantidade:").grid(row=4, column=0, sticky="w")
        self.qty_var = tk.StringVar(value="0")
        ttk.Entry(frm, textvariable=self.qty_var).grid(row=4, column=1, sticky="ew")

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=2, pady=(8,0))
        ttk.Button(btns, text="Salvar", command=self.save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancelar", command=self.destroy).pack(side="left", padx=4)

    def load_product(self):
        self.code_var.set(self.product["code"])
        self.name_var.set(self.product["name"])
        self.desc_text.insert("1.0", self.product["description"] or "")
        self.price_var.set(f"{self.product['price']:.2f}")
        self.qty_var.set(str(self.product["quantity"]))

    def save(self):
        code = self.code_var.get().strip()
        name = self.name_var.get().strip()
        desc = self.desc_text.get("1.0","end").strip()
        try:
            price = float(self.price_var.get().strip() or 0)
        except:
            messagebox.showerror("Erro", "Preço inválido.")
            return
        try:
            qty = int(self.qty_var.get().strip() or 0)
        except:
            messagebox.showerror("Erro", "Quantidade inválida.")
            return
        if not name:
            messagebox.showerror("Erro", "Nome obrigatório.")
            return
        data = {"code": code, "name": name, "description": desc, "price": price, "quantity": qty}
        if self.on_save:
            self.on_save(data)
        self.destroy()

class StockDialog(simpledialog.Dialog):
    def __init__(self, parent, product, ttype, on_save):
        self.product = product
        self.ttype = ttype
        self.on_save = on_save
        super().__init__(parent, title=f"{'Entrada' if ttype=='in' else 'Saída'} - {product['name']}")

    def body(self, master):
        ttk.Label(master, text=f"Produto: {self.product['name']} (Qtd atual: {self.product['quantity']})").pack(padx=8, pady=6)
        frm = ttk.Frame(master)
        frm.pack(padx=8, pady=4)
        ttk.Label(frm, text="Quantidade:").grid(row=0, column=0)
        self.qty_var = tk.StringVar(value="1")
        ttk.Entry(frm, textvariable=self.qty_var).grid(row=0, column=1)
        ttk.Label(frm, text="Observação:").grid(row=1, column=0, sticky="nw")
        self.note = tk.Text(frm, width=30, height=4)
        self.note.grid(row=1, column=1)
        return None

    def apply(self):
        qty = self.qty_var.get().strip()
        note = self.note.get("1.0","end").strip()
        if self.on_save:
            self.on_save(qty, note)

class TransactionsWindow(tk.Toplevel):
    def __init__(self, parent, product_id=None):
        super().__init__(parent)
        self.product_id = product_id
        self.title("Histórico de Transações")
        self.geometry("700x400")
        self.create_widgets()
        self.refresh()

    def create_widgets(self):
        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        ttk.Label(top, text="Filtrar por produto (opcional):").pack(side="left")
        self.filter_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.filter_var).pack(side="left", padx=6)
        ttk.Button(top, text="Aplicar", command=self.refresh).pack(side="left", padx=4)
        ttk.Button(top, text="Exportar CSV", command=self.export_csv).pack(side="left", padx=4)

        self.tree = ttk.Treeview(self, columns=("product","type","quantity","note","date"), show="headings")
        self.tree.heading("product", text="Produto")
        self.tree.heading("type", text="Tipo")
        self.tree.heading("quantity", text="Quantidade")
        self.tree.heading("note", text="Observação")
        self.tree.heading("date", text="Data")
        self.tree.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        if self.product_id:
            rows = get_transactions(product_id=self.product_id)
        else:
            # apply textual filter: search product name or code
            f = self.filter_var.get().strip()
            if f:
                all_rows = get_transactions()
                rows = [r for r in all_rows if f.lower() in r["name"].lower() or f.lower() in r["code"].lower()]
            else:
                rows = get_transactions()
        for r in rows:
            t = "Entrada" if r["type"] == "in" else "Saída"
            self.tree.insert("", "end", values=(f"{r['code']} - {r['name']}", t, r["quantity"], r["note"], r["created_at"]))

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files","*.csv")])
        if not path:
            return
        rows = get_transactions(product_id=self.product_id)
        with open(path, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id","product_code","product_name","type","quantity","note","created_at"])
            for r in rows:
                writer.writerow([r["id"], r["code"], r["name"], r["type"], r["quantity"], r["note"], r["created_at"]])
        messagebox.showinfo("Exportado", f"Histórico exportado para {os.path.basename(path)}")


# Main

def main():
    init_db()
    root = tk.Tk()
    # estilo ttk básico
    style = ttk.Style(root)
    try:
        style.theme_use('clam')
    except:
        pass
    app = InventoryApp(root)
    root.geometry("900x500")
    root.mainloop()

if __name__ == "__main__":
    main()
