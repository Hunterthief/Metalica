# metal_inventory.py
# -*- coding: utf-8 -*-
"""
برنامج إدارة مخزون المعادن - نسخة أساسية (Tkinter)
ميزات: إضافة معدن، إضافة كمية، سحب/بيع، سجل، تصدير/استيراد JSON، نسخ احتياطي تلقائي.
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

# تهيئة مجلد النسخ الاحتياطية
os.makedirs(BACKUP_DIR, exist_ok=True)

def now_iso():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

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
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = os.path.join(BACKUP_DIR, f"backup_{ts}.json")
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filename
    except Exception as e:
        print("Backup failed:", e)
        return None

# برنامج الجدولة للنسخ الاحتياطي (خيط منفصل)
def start_auto_backup(app):
    def loop():
        while True:
            try:
                data = app.data
                make_backup(data)
                # عدِّل الوقت هنا إذا أردت اختبار بسرعة
            except Exception as e:
                print("Auto-backup error:", e)
            # انتظار
            threading.Event().wait(AUTO_BACKUP_INTERVAL_SECONDS)
    t = threading.Thread(target=loop, daemon=True)
    t.start()


class MetalInventoryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("إدارة مخزون المعادن")
        self.geometry("900x600")
        # استخدام خط عربي مناسب إن وُجد
        default_font = ("Cairo", 11)
        self.option_add("*Font", default_font)

        # بيانات
        self.data = load_data()
        # تحقق من وجود نسخة احتياطية مؤخّرة إن انغلق البرنامج بشكل غير متوقع
        self.check_restore_on_start()

        # واجهة
        self.create_widgets()
        self.refresh_table()
        # بدء النسخ الاحتياطي التلقائي في خيط مستقل
        start_auto_backup(self)

    def check_restore_on_start(self):
        # فحص إن كان هناك ملف نسخة احتياطية أحدث من آخر حفظ
        backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("backup_")])
        if backups:
            latest = backups[-1]
            latest_path = os.path.join(BACKUP_DIR, latest)
            # اسأل المستخدم إن أراد استعادة النسخة
            if messagebox.askyesno("استعادة", f"هل تريد استعادة آخر نسخة احتياطية ({latest})؟"):
                try:
                    with open(latest_path, "r", encoding="utf-8") as f:
                        self.data = json.load(f)
                    save_data(self.data)
                    messagebox.showinfo("تم", "تم استعادة النسخة الاحتياطية.")
                except Exception as e:
                    messagebox.showerror("خطأ", f"فشل استعادة النسخة: {e}")

    def create_widgets(self):
        # شريط علوي للأزرار
        top_frame = ttk.Frame(self)
        top_frame.pack(fill=tk.X, padx=8, pady=6)

        btn_add_metal = ttk.Button(top_frame, text="➕ إضافة معدن جديد", command=self.open_add_metal)
        btn_add_stock = ttk.Button(top_frame, text="📦 إضافة كمية", command=self.open_add_stock)
        btn_remove_stock = ttk.Button(top_frame, text="💰 بيع / سحب كمية", command=self.open_remove_stock)
        btn_history = ttk.Button(top_frame, text="🕒 السجل", command=self.open_history_window)
        btn_export = ttk.Button(top_frame, text="⬇️ تصدير", command=self.export_data)
        btn_import = ttk.Button(top_frame, text="⬆️ استيراد", command=self.import_data)
        btn_settings = ttk.Button(top_frame, text="⚙️ الإعدادات", command=self.open_settings)

        # ترتيب من اليمين لليسار: نضع الأزرار في ترتيب مرن
        for w in [btn_settings, btn_import, btn_export, btn_history, btn_remove_stock, btn_add_stock, btn_add_metal]:
            w.pack(side=tk.RIGHT, padx=4)

        # شريط بحث
        search_frame = ttk.Frame(self)
        search_frame.pack(fill=tk.X, padx=8)
        ttk.Label(search_frame, text="بحث:").pack(side=tk.RIGHT, padx=4)
        self.search_var = tk.StringVar()
        entry_search = ttk.Entry(search_frame, textvariable=self.search_var, justify="right")
        entry_search.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        entry_search.bind("<KeyRelease>", lambda e: self.refresh_table())

        # جدول عرض المعادن (Listbox + تفاصيل)
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
            self.tree.insert("", "end", iid=name, values=(qty, price, value, last, source), text=name)
            # ضع اسم العنصر كـ label على يسار السطر
            self.tree.set(name, column="#0", value=name)
        self.total_value_label.config(text=f"إجمالي قيمة المخزون: {total_value} جنيه")
        # آخر نسخة احتياطية: نعرض آخر ملف داخل المجلد
        backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("backup_")])
        last = backups[-1] if backups else "-"
        self.last_backup_label.config(text=f"آخر نسخة احتياطية: {last}")

    def on_item_double_click(self, event):
        item = self.tree.focus()
        if item:
            # عرض تفاصيل أو نافذة التعديل البسيط
            name = item
            metal = next((m for m in self.data["metals"] if m["name"]==name), None)
            if metal:
                info = f"المعدن: {metal['name']}\nالكمية: {metal['quantity']} كجم\nالسعر لكل كجم: {metal['price_per_kg']} جنيه\nالمورد: {metal.get('source','')}\nآخر تحديث: {metal.get('last_updated','')}"
                messagebox.showinfo("تفاصيل معدن", info)

    # ---------- العمليات الأساسية ----------
    def open_add_metal(self):
        dialog = AddMetalDialog(self)
        self.wait_window(dialog.top)
        if dialog.result:
            name, qty, price, source = dialog.result
            # تحقق إن المعدن موجود مسبقًا
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
            # سجل
            self.data.setdefault("history", []).append({
                "operation": "Add Metal",
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

    def open_add_stock(self):
        dialog = AddOrRemoveDialog(self, mode="add")
        self.wait_window(dialog.top)
        if dialog.result:
            name, qty, price, person, total = dialog.result
            metal = next((m for m in self.data["metals"] if m["name"]==name), None)
            if not metal:
                messagebox.showerror("خطأ", "المعدن غير موجود.")
                return
            metal["quantity"] = round(float(metal.get("quantity",0)) + float(qty), 3)
            metal["price_per_kg"] = float(price)
            metal["source"] = person
            metal["last_updated"] = now_iso()
            self.data.setdefault("history", []).append({
                "operation": "Add Stock",
                "metal": name,
                "quantity": float(qty),
                "price_per_kg": float(price),
                "total_price": float(total),
                "person": person,
                "date": now_iso()
            })
            save_data(self.data)
            make_backup(self.data)
            self.refresh_table()

    def open_remove_stock(self):
        dialog = AddOrRemoveDialog(self, mode="remove")
        self.wait_window(dialog.top)
        if dialog.result:
            name, qty, price, person, total = dialog.result
            metal = next((m for m in self.data["metals"] if m["name"]==name), None)
            if not metal:
                messagebox.showerror("خطأ", "المعدن غير موجود.")
                return
            if float(qty) > float(metal.get("quantity",0)):
                messagebox.showerror("خطأ", "الكمية المسحوبة أكبر من المتوفر.")
                return
            metal["quantity"] = round(float(metal.get("quantity",0)) - float(qty), 3)
            metal["price_per_kg"] = float(price)
            metal["last_updated"] = now_iso()
            self.data.setdefault("history", []).append({
                "operation": "Remove Stock",
                "metal": name,
                "quantity": float(qty),
                "price_per_kg": float(price),
                "total_price": float(total),
                "person": person,
                "date": now_iso()
            })
            save_data(self.data)
            make_backup(self.data)
            self.refresh_table()

    def open_history_window(self):
        HistoryWindow(self, self.data.get("history", []))

    # استيراد/تصدير
    def export_data(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON","*.json")], title="حفظ البيانات كـ JSON")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("تم", "تم حفظ البيانات.")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل الحفظ: {e}")

    def import_data(self):
        path = filedialog.askopenfilename(filetypes=[("JSON","*.json")], title="اختر ملف JSON للاستيراد")
        if not path:
            return
        if not messagebox.askyesno("تأكيد", "سيتم استبدال جميع البيانات الحالية. هل ترغب بالمتابعة؟"):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            # تحقق بسيط لبنية الملف
            if "metals" in d and "history" in d:
                self.data = d
                save_data(self.data)
                make_backup(self.data)
                self.refresh_table()
                messagebox.showinfo("تم", "تم استيراد البيانات.")
            else:
                messagebox.showerror("خطأ", "بنية الملف غير صحيحة.")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل الاستيراد: {e}")

    def open_settings(self):
        messagebox.showinfo("إعدادات", "لا يوجد إعدادات متقدمة حالياً.\nيمكن إضافة كلمة مرور أو إعدادات متقدمة في التحديث القادم.")

# ----- نوافذ الحوار -----
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

class AddOrRemoveDialog:
    def __init__(self, parent, mode="add"):
        self.mode = mode
        top = self.top = tk.Toplevel(parent)
        top.title("إضافة كمية" if mode=="add" else "بيع / سحب كمية")
        top.transient(parent)
        top.grab_set()
        ttk.Label(top, text="اختر المعدن:").grid(row=0, column=0, sticky="e")
        self.metal_var = tk.StringVar()
        metals = [m["name"] for m in parent.data.get("metals",[])]
        self.cmb = ttk.Combobox(top, values=metals, textvariable=self.metal_var, state="readonly", justify="right")
        self.cmb.grid(row=0, column=1, pady=4)
        ttk.Label(top, text="الكمية (كجم):").grid(row=1, column=0, sticky="e")
        self.e_qty = ttk.Entry(top, justify="right")
        self.e_qty.grid(row=1, column=1, pady=4)
        ttk.Label(top, text="السعر لكل كجم:").grid(row=2, column=0, sticky="e")
        self.e_price = ttk.Entry(top, justify="right")
        self.e_price.grid(row=2, column=1, pady=4)
        ttk.Label(top, text="الطرف (مورد/عميل):").grid(row=3, column=0, sticky="e")
        self.e_person = ttk.Entry(top, justify="right")
        self.e_person.grid(row=3, column=1, pady=4)
        ttk.Label(top, text="السعر الإجمالي:").grid(row=4, column=0, sticky="e")
        self.e_total = ttk.Entry(top, justify="right")
        self.e_total.grid(row=4, column=1, pady=4)
        btn_ok = ttk.Button(top, text="تأكيد", command=self.on_ok)
        btn_cancel = ttk.Button(top, text="إلغاء", command=self.on_cancel)
        btn_ok.grid(row=5, column=1, sticky="e", pady=6)
        btn_cancel.grid(row=5, column=0, sticky="w", pady=6)
        self.result = None

    def on_ok(self):
        name = self.metal_var.get().strip()
        qty = self.e_qty.get().strip()
        price = self.e_price.get().strip()
        person = self.e_person.get().strip()
        total = self.e_total.get().strip()
        if not name or not qty or not price:
            messagebox.showerror("خطأ", "يرجى ملء الحقول المطلوبة.")
            return
        try:
            float(qty); float(price)
            if total:
                float(total)
            else:
                total = round(float(qty) * float(price), 2)
        except:
            messagebox.showerror("خطأ", "قيمة رقمية خاطئة.")
            return
        self.result = (name, qty, price, person, float(total))
        self.top.destroy()

    def on_cancel(self):
        self.top.destroy()

class HistoryWindow:
    def __init__(self, parent, history):
        top = self.top = tk.Toplevel(parent)
        top.title("السجل")
        top.geometry("800x500")
        # شريط أدوات لتصدير
        tool = ttk.Frame(top)
        tool.pack(fill=tk.X, padx=6, pady=6)
        ttk.Button(tool, text="تصدير CSV", command=lambda: self.export_csv(history)).pack(side=tk.LEFT, padx=4)
        ttk.Button(tool, text="تصدير JSON", command=lambda: self.export_json(history)).pack(side=tk.LEFT, padx=4)

        cols = ("date","operation","metal","quantity","price_per_kg","total_price","person")
        tree = ttk.Treeview(top, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, anchor="center")
        vsb = ttk.Scrollbar(top, orient="vertical", command=tree.yview)
        tree.configure(yscroll=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        for h in history:
            tree.insert("", "end", values=(h.get("date"), h.get("operation"), h.get("metal"), h.get("quantity"), h.get("price_per_kg"), h.get("total_price"), h.get("person")))

    def export_csv(self, history):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["date","operation","metal","quantity","price_per_kg","total_price","person"])
                for h in history:
                    writer.writerow([h.get("date"), h.get("operation"), h.get("metal"), h.get("quantity"), h.get("price_per_kg"), h.get("total_price"), h.get("person")])
            messagebox.showinfo("تم", "تم تصدير السجل CSV.")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل التصدير: {e}")

    def export_json(self, history):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON","*.json")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("تم", "تم تصدير السجل JSON.")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل التصدير: {e}")

if __name__ == "__main__":
    app = MetalInventoryApp()
    app.mainloop()
