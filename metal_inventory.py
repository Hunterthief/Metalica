# metal_inventory.py
# -*- coding: utf-8 -*-
"""
برنامج إدارة مخزون المعادن - Metalica (Tkinter)
ميزات: إضافة معدن جديد أو موجود، إضافة كمية، سحب/بيع، سجل بالعربية، تصدير/استيراد JSON، نسخ احتياطي تلقائي بصيغة AM/PM.
"""

import os
import json
import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from datetime import datetime
import threading

# إعدادات
DATA_FILE = "data.json"
BACKUP_DIR = "backups"
AUTO_BACKUP_INTERVAL_SECONDS = 30 * 60  # 30 دقيقة

os.makedirs(BACKUP_DIR, exist_ok=True)

def now_iso():
    return datetime.now().strftime("%Y-%m-%dT%I:%M:%S %p")  # AM/PM

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل قراءة ملف البيانات: {e}")
            return {"metals": [], "history": []}
    else:
        return {"metals": [], "history": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def make_backup(data):
    ts = datetime.now().strftime("%Y-%m-%d_%I-%M-%p")
    filename = os.path.join(BACKUP_DIR, f"backup_{ts}.json")
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filename
    except Exception as e:
        print("Backup failed:", e)
        return None

def start_auto_backup(app):
    def loop():
        while True:
            try:
                data = app.data
                make_backup(data)
            except Exception as e:
                print("Auto-backup error:", e)
            threading.Event().wait(AUTO_BACKUP_INTERVAL_SECONDS)
    t = threading.Thread(target=loop, daemon=True)
    t.start()

# ===========================
# التطبيق الرئيسي
# ===========================
class MetalInventoryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Metalica")
        self.geometry("900x600")
        self.option_add("*Font", ("Cairo", 11))
        self.data = load_data()
        self.check_restore_on_start()
        self.create_widgets()
        self.refresh_table()
        start_auto_backup(self)

    def check_restore_on_start(self):
        backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("backup_")])
        if backups:
            latest = backups[-1]
            latest_path = os.path.join(BACKUP_DIR, latest)
            if messagebox.askyesno("استعادة", f"هل تريد استعادة آخر نسخة احتياطية ({latest})؟"):
                try:
                    with open(latest_path, "r", encoding="utf-8") as f:
                        self.data = json.load(f)
                    save_data(self.data)
                    messagebox.showinfo("تم", "تم استعادة النسخة الاحتياطية.")
                except Exception as e:
                    messagebox.showerror("خطأ", f"فشل استعادة النسخة: {e}")

    # ---------------------------
    # واجهة المستخدم
    # ---------------------------
    def create_widgets(self):
        top_frame = ttk.Frame(self)
        top_frame.pack(fill=tk.X, padx=8, pady=6)

        self.btn_add_metal = ttk.Button(top_frame, text="➕ إضافة معدن", command=self.open_add_metal_menu)
        self.btn_add_stock = ttk.Button(top_frame, text="📦 إضافة كمية", command=self.open_add_stock)
        self.btn_remove_stock = ttk.Button(top_frame, text="💰 بيع / سحب كمية", command=self.open_remove_stock)
        self.btn_history = ttk.Button(top_frame, text="🕒 السجل", command=self.open_history_window)
        self.btn_export = ttk.Button(top_frame, text="⬇️ تصدير", command=self.export_data)
        self.btn_import = ttk.Button(top_frame, text="⬆️ استيراد", command=self.import_data)
        self.btn_settings = ttk.Button(top_frame, text="⚙️ الإعدادات", command=self.open_settings)

        for w in [self.btn_settings, self.btn_import, self.btn_export, self.btn_history, self.btn_remove_stock, self.btn_add_stock, self.btn_add_metal]:
            w.pack(side=tk.RIGHT, padx=4)

        # تعطيل زر إضافة معدن موجود إذا لم يكن هناك معادن
        self.btn_add_existing_state = tk.NORMAL if self.data.get("metals") else tk.DISABLED

        # شريط البحث
        search_frame = ttk.Frame(self)
        search_frame.pack(fill=tk.X, padx=8)
        ttk.Label(search_frame, text="بحث:").pack(side=tk.RIGHT, padx=4)
        self.search_var = tk.StringVar()
        entry_search = ttk.Entry(search_frame, textvariable=self.search_var, justify="right")
        entry_search.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        entry_search.bind("<KeyRelease>", lambda e: self.refresh_table())

        # جدول المعادن
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        self.tree = ttk.Treeview(main_frame, columns=("quantity", "price", "value", "last", "source"), show="headings")
        self.tree.heading("quantity", text="الكمية (كجم)")
        self.tree.heading("price", text="السعر لكل كجم (جنيه)")
        self.tree.heading("value", text="القيمة الإجمالية")
        self.tree.heading("last", text="آخر تحديث")
        self.tree.heading("source", text="المورد الأخير")

        self.tree.column("quantity", anchor="center", width=120)
        self.tree.column("price", anchor="center", width=140)
        self.tree.column("value", anchor="center", width=140)
        self.tree.column("last", anchor="center", width=160)
        self.tree.column("source", anchor="center", width=180)

        vsb = ttk.Scrollbar(main_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.tree.bind("<Double-1>", self.on_item_double_click)

        # شريط الحالة السفلي
        status_frame = ttk.Frame(self)
        status_frame.pack(fill=tk.X, padx=8, pady=6)
        self.last_backup_label = ttk.Label(status_frame, text="آخر نسخة احتياطية: -")
        self.total_value_label = ttk.Label(status_frame, text="إجمالي قيمة المخزون: 0 جنيه")
        self.last_backup_label.pack(side=tk.RIGHT, padx=8)
        self.total_value_label.pack(side=tk.LEFT, padx=8)

    # ---------------------------
    # إضافة معدن: نافذة اختيار نوع الإضافة
    # ---------------------------
    def open_add_metal_menu(self):
        menu = tk.Toplevel(self)
        menu.title("اختيار العملية")
        menu.transient(self)
        menu.grab_set()
        ttk.Label(menu, text="اختر نوع الإضافة:").pack(pady=10)

        btn_new = ttk.Button(menu, text="➕ معدن جديد", command=lambda:[menu.destroy(), self.open_add_metal_dialog()])
        btn_new.pack(pady=5)

        btn_existing = ttk.Button(menu, text="⬆️ إضافة لمعدن موجود", state=self.btn_add_existing_state,
                                  command=lambda:[menu.destroy(), self.open_add_stock()])
        btn_existing.pack(pady=5)

    # ---------------------------
    # إضافة معدن جديد
    # ---------------------------
    def open_add_metal_dialog(self):
        dialog = AddMetalDialog(self)
        self.wait_window(dialog.top)
        if dialog.result:
            name, qty, price, source = dialog.result
            existing = next((m for m in self.data["metals"] if m["name"]==name), None)
            if existing:
                messagebox.showwarning("تحذير", "هذا المعدن موجود مسبقًا. استخدم إضافة كمية لزيادة المخزون.")
                return
            m = {
                "name": name,
                "quantity": float(qty),
                "price_per_kg": float(price),
                "source": source,
                "last_updated": now_iso()
            }
            self.data.setdefault("metals", []).append(m)
            self.data.setdefault("history", []).append({
                "operation": "إضافة معدن جديد",
                "metal": name,
                "quantity": float(qty),
                "price_per_kg": float(price),
                "total_price": round(float(qty)*float(price),2),
                "person": source,
                "date": now_iso()
            })
            save_data(self.data)
            make_backup(self.data)
            self.refresh_table()
            # تفعيل زر إضافة معدن موجود بعد أول معدن
            self.btn_add_existing_state = tk.NORMAL

    # ---------------------------
    # تحديث جدول المعادن
    # ---------------------------
    def refresh_table(self):
        q = self.search_var.get().strip()
        for i in self.tree.get_children():
            self.tree.delete(i)
        total_value = 0.0
        for m in self.data.get("metals", []):
            name = m.get("name", "")
            if q and (q not in name and q not in (m.get("source",""))):
                continue
            qty = m.get("quantity", 0)
            price = m.get("price_per_kg", 0)
            value = round(qty * price, 2)
            total_value += value
            last = m.get("last_updated", "")
            source = m.get("source", "")
            self.tree.insert("", "end", iid=name, values=(qty, price, value, last, source))
        self.total_value_label.config(text=f"إجمالي قيمة المخزون: {total_value} جنيه")
        backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("backup_")])
        last = backups[-1] if backups else "-"
        self.last_backup_label.config(text=f"آخر نسخة احتياطية: {last}")

    # ---------------------------
    # عرض تفاصيل معدن عند النقر المزدوج
    # ---------------------------
    def on_item_double_click(self, event):
        item = self.tree.focus()
        if item:
            name = item
            metal = next((m for m in self.data["metals"] if m["name"]==name), None)
            if metal:
                info = f"المعدن: {metal['name']}\nالكمية: {metal['quantity']} كجم\nالسعر لكل كجم: {metal['price_per_kg']} جنيه\nالمورد: {metal.get('source','')}\nآخر تحديث: {metal.get('last_updated','')}"
                messagebox.showinfo("تفاصيل معدن", info)

    # ---------------------------
    # فتح سجل بالعربية
    # ---------------------------
    def open_history_window(self):
        HistoryWindow(self, self.data.get("history", []))

    # ---------------------------
    # استيراد وتصدير
    # ---------------------------
    def export_data(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON","*.json")], title="حفظ البيانات كـ JSON")
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("تم", "تم حفظ البيانات.")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل الحفظ: {e}")

    def import_data(self):
        path = filedialog.askopenfilename(filetypes=[("JSON","*.json")], title="اختر ملف JSON للاستيراد")
        if not path: return
        if not messagebox.askyesno("تأكيد", "سيتم استبدال جميع البيانات الحالية. هل ترغب بالمتابعة؟"):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if "metals" in d and "history" in d:
                self.data = d
                save_data(self.data)
                make_backup(self.data)
                self.refresh_table()
                messagebox.showinfo("تم", "تم استيراد البيانات.")
                self.btn_add_existing_state = tk.NORMAL if self.data.get("metals") else tk.DISABLED
            else:
                messagebox.showerror("خطأ", "بنية الملف غير صحيحة.")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل الاستيراد: {e}")

    def open_settings(self):
        messagebox.showinfo("إعدادات", "لا يوجد إعدادات متقدمة حالياً.\nيمكن إضافة كلمة مرور أو إعدادات متقدمة في التحديث القادم.")

# ===========================
# نوافذ الحوار
# ===========================
class AddMetalDialog:
    def __init__(self, parent):
        top = self.top = tk.Toplevel(parent)
        top.title("إضافة معدن جديد")
        top.transient(parent)
        top.grab_set()
        ttk.Label(top, text="اسم المعدن:").grid(row=0, column=0, sticky="e")
        self.e_name = ttk.Entry(top, justify="right")
        self.e_name.grid(row=0, column=1, pady=4)
        ttk.Label(top, text="الكمية الابتدائية (كجم):").grid(row=1, column=0, sticky="e")
        self.e_qty = ttk.Entry(top, justify="right")
        self.e_qty.grid(row=1, column=1, pady=4)
        ttk.Label(top, text="السعر لكل كجم (جنيه):").grid(row=2, column=0, sticky="e")
        self.e_price = ttk.Entry(top, justify="right")
        self.e_price.grid(row=2, column=1, pady=4)
        ttk.Label(top, text="اسم المورد:").grid(row=3, column=0, sticky="e")
        self.e_source = ttk.Entry(top, justify="right")
        self.e_source.grid(row=3, column=1, pady=4)
        btn_save = ttk.Button(top, text="حفظ", command=self.on_save)
        btn_cancel = ttk.Button(top, text="إلغاء", command=self.on_cancel)
        btn_save.grid(row=4, column=1, sticky="e", pady=6)
        btn_cancel.grid(row=4, column=0, sticky="w", pady=6)
        self.result = None

    def on_save(self):
        name = self.e_name.get().strip()
        qty = self.e_qty.get().strip()
        price = self.e_price.get().strip()
        source = self.e_source.get().strip()
        if not name or not qty or not price:
            messagebox.showerror("خطأ", "يرجى ملء الحقول المطلوبة.")
            return
        try:
            float(qty); float(price)
        except:
            messagebox.showerror("خطأ", "الكمية أو السعر غير صالحين.")
            return
        self.result = (name, qty, price, source)
        self.top.destroy()

    def on_cancel(self):
        self.top.destroy()

class HistoryWindow:
    def __init__(self, parent, history):
        top = self.top = tk.Toplevel(parent)
        top.title("السجل")
        top.geometry("800x500")

        tool = ttk.Frame(top)
        tool.pack(fill=tk.X, padx=6, pady=6)
        ttk.Button(tool, text="تصدير CSV", command=lambda: self.export_csv(history)).pack(side=tk.LEFT, padx=4)
        ttk.Button(tool, text="تصدير JSON", command=lambda: self.export_json(history)).pack(side=tk.LEFT, padx=4)

        cols = ("date","operation","metal","quantity","price_per_kg","total_price","person")
        headers_ar = {
            "date":"التاريخ",
            "operation":"العملية",
            "metal":"المعدن",
            "quantity":"الكمية",
            "price_per_kg":"السعر لكل كجم",
            "total_price":"السعر الإجمالي",
            "person":"المورد/العميل"
        }

        tree = ttk.Treeview(top, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=headers_ar[c])
            tree.column(c, anchor="center")
        vsb = ttk.Scrollbar(top, orient="vertical", command=tree.yview)
        tree.configure(yscroll=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        for h in history:
            tree.insert("", "end", values=(
                h.get("date"),
                h.get("operation"),
                h.get("metal"),
                h.get("quantity"),
                h.get("price_per_kg"),
                h.get("total_price"),
                h.get("person")
            ))

    def export_csv(self, history):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
        if not path: return
        try:
            with open(path, "w", encoding="utf-8", newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["التاريخ","العملية","المعدن","الكمية","السعر لكل كجم","السعر الإجمالي","المورد/العميل"])
                for h in history:
                    writer.writerow([h.get("date"), h.get("operation"), h.get("metal"), h.get("quantity"), h.get("price_per_kg"), h.get("total_price"), h.get("person")])
            messagebox.showinfo("تم", "تم تصدير السجل CSV.")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل التصدير: {e}")

    def export_json(self, history):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON","*.json")])
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("تم", "تم تصدير السجل JSON.")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل التصدير: {e}")

if __name__ == "__main__":
    app = MetalInventoryApp()
    app.mainloop()
