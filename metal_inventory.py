# metal_inventory.py
# -*- coding: utf-8 -*-
"""
برنامج إدارة مخزون المعادن - Metalica (Tkinter)
ميزات:
 - إضافة معدن جديد أو إضافة كمية لمعدن موجود
 - تتبع مصادر منفصلة (lots) لكل معدن (كل مصدر/دفعة يحتفظ بكمية وسعر شراء)
 - بيع/سحب كمية مع احتساب cost-basis (FIFO) وحساب الربح لكل معدن وإجمالي الربح
 - سجل بالعربية، تصدير CSV/JSON، استيراد JSON
 - نسخ احتياطي تلقائي بأسماء ملفات بصيغة AM/PM
 - نافذة السجل تُفتح مكبَّرة
 - تعديل أسعار (سعر شراء افتراضي لكل معدن، سعر بيع افتراضي)
 - عند إغلاق البرنامج، يسأل المستخدم ما إذا كان يريد إنشاء نسخة احتياطية قبل الإغلاق
"""

import os
import json
import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import threading

# إعدادات الملفات
DATA_FILE = "data.json"
BACKUP_DIR = "backups"
AUTO_BACKUP_INTERVAL_SECONDS = 30 * 60  # 30 دقيقة

os.makedirs(BACKUP_DIR, exist_ok=True)

# ---------------------------------------------------------------------
# الدوال العامة
# ---------------------------------------------------------------------
def now_iso():
    """تاريخ ووقت بصيغة ISO مع AM/PM"""
    return datetime.now().strftime("%Y-%m-%dT%I:%M:%S %p")

def backup_timestamp():
    """تاريخ ووقت لاسم النسخة الاحتياطية"""
    return datetime.now().strftime("%Y-%m-%d_%I-%M-%p")

def load_data():
    """تحميل البيانات من data.json"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            if "metals" not in d:
                d["metals"] = []
            if "history" not in d:
                d["history"] = []
            # تحديث البنية إذا كانت قديمة
            for m in d.get("metals", []):
                if "lots" not in m:
                    lots = []
                    if m.get("quantity", 0) and (m.get("price_per_kg", None) is not None):
                        src = m.get("source", "مصدر افتراضي")
                        qty = float(m.get("quantity", 0))
                        total_paid = round(qty * float(m.get("price_per_kg", 0)), 2)
                        lots.append({
                            "source": src,
                            "quantity": qty,
                            "total_paid": total_paid,
                            "date": m.get("last_updated", now_iso())
                        })
                    m["lots"] = lots
                if "price_per_kg" not in m:
                    m["price_per_kg"] = 0.0
                if "sale_price_per_kg" not in m:
                    m["sale_price_per_kg"] = m.get("price_per_kg", 0.0)
                if "profit_total" not in m:
                    m["profit_total"] = 0.0
            return d
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل قراءة ملف البيانات: {e}")
            return {"metals": [], "history": []}
    else:
        return {"metals": [], "history": []}

def save_data(data):
    """حفظ البيانات إلى data.json"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def make_backup(data):
    """إنشاء نسخة احتياطية جديدة"""
    ts = backup_timestamp()
    filename = os.path.join(BACKUP_DIR, f"backup_{ts}.json")
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filename
    except Exception as e:
        print("Backup failed:", e)
        return None

def start_auto_backup(app):
    """بدء النسخ الاحتياطي التلقائي"""
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

# ---------------------------------------------------------------------
# دوال المساعدة
# ---------------------------------------------------------------------
def metal_total_quantity(metal):
    """احسب إجمالي الكمية المتاحة من جميع المصادر"""
    return round(sum(l.get("quantity", 0.0) for l in metal.get("lots", [])), 6)

def metal_total_paid(metal):
    """احسب إجمالي المبلغ المدفوع لكل المعدن"""
    return round(sum(l.get("total_paid", 0.0) for l in metal.get("lots", [])), 2)

def deduct_from_lots(metal, qty_to_remove):
    """خصم كمية من المخزون (FIFO) وارجاع التكلفة"""
    remaining = qty_to_remove
    cost = 0.0
    new_lots = []
    for lot in metal.get("lots", []):
        if remaining <= 0:
            new_lots.append(lot)
            continue
        lot_qty = float(lot.get("quantity", 0.0))
        lot_paid = float(lot.get("total_paid", 0.0))
        if lot_qty <= 0:
            new_lots.append(lot)
            continue
        if lot_qty <= remaining + 1e-9:
            cost += lot_paid
            remaining -= lot_qty
        else:
            portion = remaining / lot_qty
            part_paid = lot_paid * portion
            cost += part_paid
            new_qty = lot_qty - remaining
            new_total_paid = lot_paid - part_paid
            new_lot = {
                "source": lot["source"],
                "quantity": round(new_qty,6),
                "total_paid": round(new_total_paid,2),
                "date": lot.get("date")
            }
            new_lots.append(new_lot)
            remaining = 0
    if remaining > 1e-9:
        raise ValueError("الكمية المطلوبة للسحب أكبر من المتوفر.")
    metal["lots"] = new_lots
    return round(cost, 2)

# ---------------------------------------------------------------------
# التطبيق الرئيسي
# ---------------------------------------------------------------------
class MetalInventoryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Metalica")
        self.geometry("1000x650")
        self.option_add("*Font", ("Cairo", 11))
        self.data = load_data()
        self.check_restore_on_start()
        self.create_widgets()
        self.refresh_table()
        start_auto_backup(self)
        self.protocol("WM_DELETE_WINDOW", self.on_exit)  # عند الإغلاق

    # -----------------------------------------------------------------
    # عند بدء التشغيل
    # -----------------------------------------------------------------
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

    # -----------------------------------------------------------------
    # واجهة المستخدم
    # -----------------------------------------------------------------
    def create_widgets(self):
        top_frame = ttk.Frame(self)
        top_frame.pack(fill=tk.X, padx=8, pady=6)

        self.btn_add_metal = ttk.Button(top_frame, text="➕ إضافة معدن", command=self.open_add_metal_menu)
        self.btn_add_stock = ttk.Button(top_frame, text="📦 إضافة كمية", command=self.open_add_stock)
        self.btn_remove_stock = ttk.Button(top_frame, text="💰 بيع / سحب كمية", command=self.open_remove_stock)
        self.btn_history = ttk.Button(top_frame, text="🕒 السجل", command=self.open_history_window)
        self.btn_export = ttk.Button(top_frame, text="⬇️ تصدير", command=self.export_data)
        self.btn_import = ttk.Button(top_frame, text="⬆️ استيراد", command=self.import_data)

        # ترتيب الأزرار من اليمين إلى اليسار
        for w in [self.btn_import, self.btn_export, self.btn_history, self.btn_remove_stock, self.btn_add_stock, self.btn_add_metal]:
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

        cols = ("name","quantity","price","value","last","sources_count")
        self.tree = ttk.Treeview(main_frame, columns=cols, show="headings")
        self.tree.heading("name", text="المعدن")
        self.tree.heading("quantity", text="الكمية (كجم)")
        self.tree.heading("price", text="سعر شراء المعدن (جنيه/كجم)")
        self.tree.heading("value", text="القيمة الإجمالية")
        self.tree.heading("last", text="آخر تحديث")
        self.tree.heading("sources_count", text="عدد المصادر")

        for c in cols:
            self.tree.column(c, anchor="center", width=150)

        vsb = ttk.Scrollbar(main_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.tree.bind("<Double-1>", self.on_item_double_click)

        # شريط الحالة السفلي
        status_frame = ttk.Frame(self)
        status_frame.pack(fill=tk.X, padx=8, pady=6)
        self.total_value_label = ttk.Label(status_frame, text="إجمالي قيمة المخزون : 0 جنيه")
        self.total_profit_label = ttk.Label(status_frame, text="إجمالي الربح: 0 جنيه")
        self.last_backup_label = ttk.Label(status_frame, text="آخر نسخة احتياطية: -")

        self.total_profit_label.pack(side=tk.LEFT, padx=8)
        self.total_value_label.pack(side=tk.LEFT, padx=8)
        self.last_backup_label.pack(side=tk.RIGHT, padx=8)

    # -----------------------------------------------------------------
    # الإغلاق الآمن
    # -----------------------------------------------------------------
    def on_exit(self):
        """يسأل المستخدم عن النسخ الاحتياطي قبل الإغلاق"""
        if messagebox.askyesno("خروج", "هل ترغب في إنشاء نسخة احتياطية قبل الإغلاق؟"):
            make_backup(self.data)
            messagebox.showinfo("تم", "تم إنشاء نسخة احتياطية بنجاح.")
        self.destroy()

    # -----------------------------------------------------------------
    # بقية الوظائف (إضافة / بيع / السجل / تصدير / استيراد)
    # -----------------------------------------------------------------
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

    def open_add_metal_dialog(self):
        dialog = AddMetalDialog(self)
        self.wait_window(dialog.top)
        if dialog.result:
            name, qty, price, source = dialog.result
            existing = next((m for m in self.data["metals"] if m["name"]==name), None)
            if existing:
                messagebox.showwarning("تحذير", "هذا المعدن موجود مسبقًا.")
                return
            m = {
                "name": name,
                "price_per_kg": float(price),
                "sale_price_per_kg": float(price),
                "lots": [],
                "last_updated": now_iso(),
                "profit_total": 0.0
            }
            if float(qty) > 0:
                total_paid = round(float(qty) * float(price), 2)
                m["lots"].append({
                    "source": source or "مصدر افتراضي",
                    "quantity": float(qty),
                    "total_paid": total_paid,
                    "date": now_iso()
                })
            self.data["metals"].append(m)
            self.data["history"].append({
                "date": now_iso(),
                "operation": "إضافة معدن جديد",
                "metal": name,
                "quantity": float(qty),
                "price_per_kg": float(price),
                "total_price": round(float(qty)*float(price),2),
                "person": source
            })
            save_data(self.data)
            make_backup(self.data)
            self.refresh_table()
            self.btn_add_existing_state = tk.NORMAL

    def open_add_stock(self):
        dialog = AddStockDialog(self, self.data.get("metals", []))
        self.wait_window(dialog.top)
        if dialog.result:
            name, qty, buy_price, source = dialog.result
            metal = next((m for m in self.data["metals"] if m["name"]==name), None)
            if not metal:
                messagebox.showerror("خطأ", "المعدن غير موجود.")
                return
            qty = float(qty)
            if buy_price is None:
                buy_price = float(metal.get("price_per_kg", 0.0))
            else:
                buy_price = float(buy_price)
            total_paid = round(qty * buy_price, 2)
            metal["lots"].append({
                "source": source or "مصدر افتراضي",
                "quantity": qty,
                "total_paid": total_paid,
                "date": now_iso()
            })
            metal["last_updated"] = now_iso()
            self.data["history"].append({
                "date": now_iso(),
                "operation": "إضافة كمية",
                "metal": name,
                "quantity": qty,
                "price_per_kg": buy_price,
                "total_price": total_paid,
                "person": source
            })
            save_data(self.data)
            make_backup(self.data)
            self.refresh_table()

    def open_remove_stock(self):
        dialog = RemoveStockDialog(self, self.data.get("metals", []))
        self.wait_window(dialog.top)
        if dialog.result:
            name, qty, sale_price, person = dialog.result
            metal = next((m for m in self.data["metals"] if m["name"]==name), None)
            if not metal:
                messagebox.showerror("خطأ", "المعدن غير موجود.")
                return
            qty = float(qty)
            total_available = metal_total_quantity(metal)
            if qty > total_available:
                messagebox.showerror("خطأ", "الكمية المسحوبة أكبر من المتوفر.")
                return
            revenue = round(qty * float(sale_price), 2)
            try:
                cost_basis = deduct_from_lots(metal, qty)
            except Exception as e:
                messagebox.showerror("خطأ", f"خطأ في خصم الكمية: {e}")
                return
            profit = round(revenue - cost_basis, 2)
            metal["profit_total"] = round(metal.get("profit_total", 0.0) + profit, 2)
            metal["last_updated"] = now_iso()
            self.data["history"].append({
                "date": now_iso(),
                "operation": "بيع / سحب كمية",
                "metal": name,
                "quantity": qty,
                "price_per_kg": float(sale_price),
                "total_price": revenue,
                "person": person,
                "cost_basis": cost_basis,
                "profit": profit
            })
            save_data(self.data)
            make_backup(self.data)
            self.refresh_table()

    def open_history_window(self):
        HistoryWindow(self, self.data.get("history", []))

    def export_data(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON","*.json")], title="حفظ البيانات كـ JSON")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("تم", "تم تصدير البيانات.")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل التصدير: {e}")

    def import_data(self):
        path = filedialog.askopenfilename(filetypes=[("JSON","*.json")], title="اختر ملف JSON للاستيراد")
        if not path:
            return
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
                messagebox.showerror("خطأ", "ملف غير صالح.")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل الاستيراد: {e}")

    # -----------------------------------------------------------------
    # عرض التفاصيل والتعديل
    # -----------------------------------------------------------------
    def refresh_table(self):
        q = self.search_var.get().strip()
        for i in self.tree.get_children():
            self.tree.delete(i)
        total_value = 0.0
        total_profit = 0.0
        for m in self.data.get("metals", []):
            name = m.get("name","")
            if q and q not in name:
                continue
            qty = metal_total_quantity(m)
            sale_price = float(m.get("sale_price_per_kg", 0.0))
            value = round(qty * sale_price, 2)
            total_value += value
            total_profit += float(m.get("profit_total", 0.0))
            last = m.get("last_updated","")
            sources_count = len(m.get("lots", []))
            self.tree.insert("", "end", iid=name, values=(name, qty, m.get("price_per_kg",0.0), value, last, sources_count))
        self.total_value_label.config(text=f"إجمالي قيمة المخزون (سعر البيع): {round(total_value,2)} جنيه")
        self.total_profit_label.config(text=f"إجمالي الربح: {round(total_profit,2)} جنيه")
        backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("backup_")])
        last = backups[-1] if backups else "-"
        self.last_backup_label.config(text=f"آخر نسخة احتياطية: {last}")

    def on_item_double_click(self, event):
        item = self.tree.focus()
        if not item:
            return
        name = item
        metal = next((m for m in self.data["metals"] if m["name"]==name), None)
        if not metal:
            return
        top = tk.Toplevel(self)
        top.title(f"تفاصيل {name} - Metalica")
        try:
            top.state("zoomed")
        except:
            try:
                top.attributes("-zoomed", True)
            except:
                pass
        frm = ttk.Frame(top, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text=f"المعدن: {metal['name']}").grid(row=0, column=0, sticky="w")
        ttk.Label(frm, text=f"الكمية الكلية: {metal_total_quantity(metal)} كجم").grid(row=1, column=0, sticky="w")
        ttk.Label(frm, text=f"سعر شراء افتراضي: {metal.get('price_per_kg',0.0)} جنيه/كجم").grid(row=2, column=0, sticky="w")
        ttk.Label(frm, text=f"سعر بيع افتراضي: {metal.get('sale_price_per_kg',0.0)} جنيه/كجم").grid(row=3, column=0, sticky="w")
        ttk.Label(frm, text=f"إجمالي المدفوع: {metal_total_paid(metal)} جنيه").grid(row=4, column=0, sticky="w")
        ttk.Label(frm, text=f"الربح الإجمالي: {metal.get('profit_total',0.0)} جنيه").grid(row=5, column=0, sticky="w")

        cols = ("source","quantity","total_paid","date")
        tree = ttk.Treeview(frm, columns=cols, show="headings", height=8)
        tree.heading("source", text="المصدر")
        tree.heading("quantity", text="الكمية (كجم)")
        tree.heading("total_paid", text="المبلغ المدفوع (جنيه)")
        tree.heading("date", text="تاريخ الإضافة")
        tree.grid(row=6, column=0, columnspan=3, pady=8, sticky="nsew")
        for lot in metal.get("lots", []):
            tree.insert("", "end", values=(lot.get("source"), lot.get("quantity"), lot.get("total_paid"), lot.get("date")))
        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=7, column=0, pady=8, sticky="w")
        ttk.Button(btn_frame, text="تعديل الأسعار", command=lambda: self.edit_prices_dialog(metal, top)).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="تصدير مصادر CSV", command=lambda: self.export_lots_csv(metal)).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="إغلاق", command=top.destroy).pack(side=tk.LEFT, padx=4)

    def edit_prices_dialog(self, metal, parent_window=None):
        top = tk.Toplevel(self)
        top.title(f"تعديل أسعار - {metal['name']}")
        top.transient(self)
        top.grab_set()
        ttk.Label(top, text="سعر الشراء الافتراضي (جنيه/كجم):").grid(row=0, column=0, sticky="e")
        e_buy = ttk.Entry(top, justify="right")
        e_buy.grid(row=0, column=1, padx=6, pady=4)
        e_buy.insert(0, str(metal.get("price_per_kg", 0.0)))
        ttk.Label(top, text="سعر البيع الافتراضي (جنيه/كجم):").grid(row=1, column=0, sticky="e")
        e_sell = ttk.Entry(top, justify="right")
        e_sell.grid(row=1, column=1, padx=6, pady=4)
        e_sell.insert(0, str(metal.get("sale_price_per_kg", metal.get("price_per_kg",0.0))))
        def save_prices():
            try:
                metal["price_per_kg"] = float(e_buy.get())
                metal["sale_price_per_kg"] = float(e_sell.get())
                metal["last_updated"] = now_iso()
                save_data(self.data)
                make_backup(self.data)
                self.refresh_table()
                top.destroy()
                if parent_window:
                    parent_window.lift()
            except Exception as e:
                messagebox.showerror("خطأ", f"قيمة غير صحيحة: {e}")
        ttk.Button(top, text="حفظ", command=save_prices).grid(row=2, column=1, sticky="e", pady=6)
        ttk.Button(top, text="إلغاء", command=top.destroy).grid(row=2, column=0, sticky="w", pady=6)

    def export_lots_csv(self, metal):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["المصدر","الكمية (كجم)","المبلغ المدفوع (جنيه)","تاريخ الإضافة"])
                for l in metal.get("lots", []):
                    writer.writerow([l.get("source"), l.get("quantity"), l.get("total_paid"), l.get("date")])
            messagebox.showinfo("تم", "تم تصدير البيانات.")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل التصدير: {e}")

# ---------------------------------------------------------------------
# نوافذ الحوارات
# ---------------------------------------------------------------------
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
        ttk.Label(top, text="السعر الافتراضي للشراء (جنيه/كجم):").grid(row=2, column=0, sticky="e")
        self.e_price = ttk.Entry(top, justify="right")
        self.e_price.grid(row=2, column=1, pady=4)
        ttk.Label(top, text="اسم المورد (اختياري):").grid(row=3, column=0, sticky="e")
        self.e_source = ttk.Entry(top, justify="right")
        self.e_source.grid(row=3, column=1, pady=4)
        ttk.Button(top, text="حفظ", command=self.on_save).grid(row=4, column=1, sticky="e", pady=6)
        ttk.Button(top, text="إلغاء", command=self.on_cancel).grid(row=4, column=0, sticky="w", pady=6)
        self.result = None
    def on_save(self):
        name = self.e_name.get().strip()
        qty = self.e_qty.get().strip() or "0"
        price = self.e_price.get().strip()
        source = self.e_source.get().strip()
        if not name or not price:
            messagebox.showerror("خطأ", "يرجى إدخال الاسم والسعر.")
            return
        try:
            float(qty); float(price)
        except:
            messagebox.showerror("خطأ", "قيمة رقمية غير صحيحة.")
            return
        self.result = (name, qty, price, source)
        self.top.destroy()
    def on_cancel(self):
        self.top.destroy()

class AddStockDialog:
    def __init__(self, parent, metals):
        top = self.top = tk.Toplevel(parent)
        top.title("إضافة كمية لمعدن موجود")
        top.transient(parent)
        top.grab_set()
        ttk.Label(top, text="اختر المعدن:").grid(row=0, column=0, sticky="e")
        self.metal_var = tk.StringVar()
        names = [m["name"] for m in metals]
        self.cmb = ttk.Combobox(top, values=names, textvariable=self.metal_var, state="readonly", justify="right")
        if names:
            self.cmb.current(0)
        self.cmb.grid(row=0, column=1, pady=4)
        ttk.Label(top, text="الكمية (كجم):").grid(row=1, column=0, sticky="e")
        self.e_qty = ttk.Entry(top, justify="right")
        self.e_qty.grid(row=1, column=1, pady=4)
        ttk.Label(top, text="سعر الشراء لكل كجم (اتركه فارغاً لاستخدام السعر الافتراضي):").grid(row=2, column=0, sticky="e")
        self.e_price = ttk.Entry(top, justify="right")
        self.e_price.grid(row=2, column=1, pady=4)
        ttk.Label(top, text="اسم المورد:").grid(row=3, column=0, sticky="e")
        self.e_source = ttk.Entry(top, justify="right")
        self.e_source.grid(row=3, column=1, pady=4)
        ttk.Button(top, text="تأكيد", command=self.on_ok).grid(row=4, column=1, sticky="e", pady=6)
        ttk.Button(top, text="إلغاء", command=self.on_cancel).grid(row=4, column=0, sticky="w", pady=6)
        self.result = None
    def on_ok(self):
        name = self.metal_var.get().strip()
        qty = self.e_qty.get().strip()
        price = self.e_price.get().strip()
        source = self.e_source.get().strip()
        if not name or not qty:
            messagebox.showerror("خطأ", "يرجى ملء الحقول المطلوبة.")
            return
        try:
            float(qty)
            if price:
                float(price)
            else:
                price = None
        except:
            messagebox.showerror("خطأ", "قيمة رقمية خاطئة.")
            return
        self.result = (name, qty, price, source)
        self.top.destroy()
    def on_cancel(self):
        self.top.destroy()

class RemoveStockDialog:
    def __init__(self, parent, metals):
        top = self.top = tk.Toplevel(parent)
        top.title("بيع / سحب كمية")
        top.transient(parent)
        top.grab_set()
        ttk.Label(top, text="اختر المعدن:").grid(row=0, column=0, sticky="e")
        self.metal_var = tk.StringVar()
        names = [m["name"] for m in metals]
        self.cmb = ttk.Combobox(top, values=names, textvariable=self.metal_var, state="readonly", justify="right")
        if names:
            self.cmb.current(0)
        self.cmb.grid(row=0, column=1, pady=4)
        ttk.Label(top, text="الكمية (كجم):").grid(row=1, column=0, sticky="e")
        self.e_qty = ttk.Entry(top, justify="right")
        self.e_qty.grid(row=1, column=1, pady=4)
        ttk.Label(top, text="سعر البيع لكل كجم (جنيه):").grid(row=2, column=0, sticky="e")
        self.e_price = ttk.Entry(top, justify="right")
        self.e_price.grid(row=2, column=1, pady=4)
        ttk.Label(top, text="الطرف (عميل/ملاحظة):").grid(row=3, column=0, sticky="e")
        self.e_person = ttk.Entry(top, justify="right")
        self.e_person.grid(row=3, column=1, pady=4)
        ttk.Button(top, text="تأكيد", command=self.on_ok).grid(row=4, column=1, sticky="e", pady=6)
        ttk.Button(top, text="إلغاء", command=self.on_cancel).grid(row=4, column=0, sticky="w", pady=6)
        self.result = None
    def on_ok(self):
        name = self.metal_var.get().strip()
        qty = self.e_qty.get().strip()
        price = self.e_price.get().strip()
        person = self.e_person.get().strip()
        if not name or not qty or not price:
            messagebox.showerror("خطأ", "يرجى ملء كل الحقول المطلوبة.")
            return
        try:
            float(qty); float(price)
        except:
            messagebox.showerror("خطأ", "قيمة رقمية خاطئة.")
            return
        self.result = (name, qty, float(price), person)
        self.top.destroy()
    def on_cancel(self):
        self.top.destroy()

class HistoryWindow:
    def __init__(self, parent, history):
        top = self.top = tk.Toplevel(parent)
        top.title("السجل - Metalica")
        try:
            top.state("zoomed")
        except:
            try:
                top.attributes("-zoomed", True)
            except:
                pass
        top.geometry("900x600")
        tool = ttk.Frame(top)
        tool.pack(fill=tk.X, padx=6, pady=6)
        ttk.Button(tool, text="تصدير CSV", command=lambda: self.export_csv(history)).pack(side=tk.LEFT, padx=4)
        ttk.Button(tool, text="تصدير JSON", command=lambda: self.export_json(history)).pack(side=tk.LEFT, padx=4)
        cols = ("date","operation","metal","quantity","price_per_kg","total_price","person","cost_basis","profit")
        headers_ar = {
            "date":"التاريخ",
            "operation":"العملية",
            "metal":"المعدن",
            "quantity":"الكمية",
            "price_per_kg":"السعر لكل كجم",
            "total_price":"القيمة الإجمالية",
            "person":"الطرف",
            "cost_basis":"تكلفة الشراء",
            "profit":"الربح"
        }
        tree = ttk.Treeview(top, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=headers_ar.get(c,c))
            tree.column(c, anchor="center")
        vsb = ttk.Scrollbar(top, orient="vertical", command=tree.yview)
        tree.configure(yscroll=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        for h in history:
            tree.insert("", "end", values=(
                h.get("date"), h.get("operation"), h.get("metal"), h.get("quantity"),
                h.get("price_per_kg"), h.get("total_price"), h.get("person"),
                h.get("cost_basis",""), h.get("profit","")
            ))
    def export_csv(self, history):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["التاريخ","العملية","المعدن","الكمية","السعر لكل كجم","القيمة الإجمالية","الطرف","تكلفة الشراء","الربح"])
                for h in history:
                    writer.writerow([h.get("date"),h.get("operation"),h.get("metal"),h.get("quantity"),h.get("price_per_kg"),h.get("total_price"),h.get("person"),h.get("cost_basis",""),h.get("profit","")])
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
    app.protocol("WM_DELETE_WINDOW", app.on_exit)
    app.mainloop()


