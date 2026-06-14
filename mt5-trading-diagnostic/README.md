# MT5 Trading Diagnostic Dashboard

مشروع Python لتحليل حسابات التداول على منصة MetaTrader 5 مباشرة، بدون الحاجة إلى طباعة تقرير من المنصة أو تصدير كشف العمليات يدوياً.

المشروع يسحب سجل العمليات من MT5، يحلل الأداء والسلوك والمخاطر، ثم ينشئ تقرير Excel وتقرير نصي عربي، وبعدها يعرض النتائج داخل Dashboard احترافي باستخدام Streamlit.

---

## فكرة المشروع

بدلاً من النظر إلى سجل التداول كأرقام فقط، هذا المشروع يحاول الإجابة على أسئلة تشخيصية مهمة مثل:

- هل الحساب رابح أم خاسر إحصائياً؟
- ما نسبة الربح؟
- ما هو Profit Factor؟
- ما متوسط الربح ومتوسط الخسارة؟
- هل يوجد Overtrading؟
- هل يوجد دخول سريع بعد الخسارة؟
- هل تم رفع حجم الصفقة بعد خسارة؟
- هل توجد سلسلة خسائر متتالية؟
- ما أفضل وأسوأ رمز؟
- ما أفضل وأسوأ وقت تداول؟
- ما المشكلة الرئيسية في سلوك المتداول؟
- ما خطة التعديل العملية للأسبوع القادم؟

---

## المخرجات الرئيسية

بعد تشغيل سكربت السحب والتحليل، يتم إنشاء مجلد باسم:

```text
mt5_direct_output_v2
```

ويحتوي على ملفات مثل:

```text
mt5_direct_diagnostic_report_v2.xlsx
diagnostic_report_ar_v2.txt
raw_deals.csv
trade_deals_clean.csv
position_summary.csv
scores.csv
client_diagnosis.csv
action_plan.csv
equity_curve.png
profit_by_symbol.png
profit_by_hour.png
```

---

## مكونات المشروع

```text
mt5-trading-diagnostic/
│
├── mt5_direct_pull_diagnostic_v2.py
├── mt5_diagnostic_dashboard.py
├── requirements.txt
├── requirements_mt5_direct_v2.txt
├── requirements_dashboard.txt
├── README.md
└── .gitignore
```

### شرح الملفات

#### `mt5_direct_pull_diagnostic_v2.py`

هذا هو السكربت المسؤول عن:

- الاتصال بمنصة MT5
- سحب سجل العمليات التاريخية
- تجهيز البيانات
- حساب مقاييس الأداء
- اكتشاف الأخطاء السلوكية
- إنشاء Scores
- إنشاء Client Diagnosis
- إنشاء Action Plan
- تصدير Excel و CSV و TXT و Charts

#### `mt5_diagnostic_dashboard.py`

هذا هو Dashboard باستخدام Streamlit، ويقرأ مخرجات سكربت التحليل من مجلد:

```text
mt5_direct_output_v2
```

ويعرض:

- KPI Cards
- Scores
- Client Diagnosis
- Behavior Flags
- Equity Curve
- Charts by symbol, hour, weekday, side
- Action Plan
- Download buttons

#### `requirements.txt`

ملف يحتوي على جميع المكتبات المطلوبة للمشروع بالكامل.

#### `requirements_mt5_direct_v2.txt`

متطلبات سكربت السحب والتحليل فقط.

#### `requirements_dashboard.txt`

متطلبات Dashboard فقط.

#### `.gitignore`

يمنع رفع ملفات محلية غير مهمة أو حساسة إلى GitHub مثل:

- ملفات البيئة الافتراضية
- ملفات النتائج
- ملفات Excel و CSV الناتجة
- ملفات Streamlit secrets

---

## المتطلبات الأساسية

### 1. نظام التشغيل

يفضل تشغيل المشروع على:

```text
Windows
```

لأن مكتبة MetaTrader5 الرسمية تعمل عادة مع منصة MT5 المثبتة على ويندوز.

---

### 2. تثبيت MetaTrader 5

يجب أن تكون منصة MetaTrader 5 مثبتة على الجهاز.

ويجب أن تكون المنصة مفتوحة ومسجل دخولك إلى الحساب المطلوب قبل تشغيل السكربت.

---

### 3. تثبيت Python

يفضل استخدام Python 3.10 أو أحدث.

للتحقق من Python:

```bash
python --version
```

للتحقق من pip:

```bash
python -m pip --version
```

إذا لم تظهر نسخة Python، تأكد أنك فعلت خيار:

```text
Add python.exe to PATH
```

أثناء تثبيت Python.

---

## تثبيت المشروع

افتح Command Prompt داخل مجلد المشروع ثم نفذ:

```bash
python -m pip install -r requirements.txt
```

إذا أردت تثبيت متطلبات السحب فقط:

```bash
python -m pip install -r requirements_mt5_direct_v2.txt
```

إذا أردت تثبيت متطلبات Dashboard فقط:

```bash
python -m pip install -r requirements_dashboard.txt
```

---

## طريقة التشغيل الكاملة

### الخطوة 1: افتح منصة MT5

قبل تشغيل السكربت:

1. افتح MetaTrader 5
2. تأكد أنك مسجل دخول في الحساب الصحيح
3. تأكد أن المنصة تعمل بدون رسائل خطأ
4. لا تغلق المنصة أثناء السحب

---

### الخطوة 2: سحب وتحليل آخر 90 يوم

من داخل مجلد المشروع شغل:

```bash
python mt5_direct_pull_diagnostic_v2.py --days 90
```

---

### الخطوة 3: سحب وتحليل آخر سنة

```bash
python mt5_direct_pull_diagnostic_v2.py --days 365
```

---

### الخطوة 4: تحديد فترة مخصصة

```bash
python mt5_direct_pull_diagnostic_v2.py --from 2026-01-01 --to 2026-06-14
```

---

### الخطوة 5: تحديد مسار منصة MT5 يدوياً

إذا لم يستطع Python العثور على منصة MT5 تلقائياً، استخدم مسار `terminal64.exe`:

```bash
python mt5_direct_pull_diagnostic_v2.py --terminal "C:\Program Files\MetaTrader 5\terminal64.exe" --days 90
```

قد يختلف المسار حسب مكان تثبيت المنصة أو اسم البروكر.

أمثلة محتملة:

```text
C:\Program Files\MetaTrader 5\terminal64.exe
C:\Program Files\Vantage Markets MT5\terminal64.exe
C:\Program Files\MetaTrader 5 Terminal\terminal64.exe
```

---

### الخطوة 6: تسجيل الدخول من السكربت

إذا أردت تمرير بيانات الدخول مباشرة:

```bash
python mt5_direct_pull_diagnostic_v2.py --login 12345678 --password "YOUR_PASSWORD" --server "Broker-Server" --days 90
```

ملاحظة مهمة: لا ترفع كلمة المرور إلى GitHub. لا تكتب بيانات الدخول داخل الكود.

---

## تشغيل Dashboard

بعد تشغيل سكربت التحليل وظهور مجلد:

```text
mt5_direct_output_v2
```

شغل Dashboard:

```bash
streamlit run mt5_diagnostic_dashboard.py
```

سيفتح المتصفح غالباً على رابط مثل:

```text
http://localhost:8501
```

---

## تشغيل Dashboard مع تحديد مجلد النتائج

إذا كان مجلد النتائج في مكان مختلف:

```bash
streamlit run mt5_diagnostic_dashboard.py -- --data-dir "C:\Users\dell\mt5_direct_output_v2"
```

مهم: وجود `-- --data-dir` بهذا الشكل ضروري لأن Streamlit يحتاج فاصل `--` قبل تمرير باراميترات للتطبيق.

---

## طريقة التشغيل من Spyder

إذا كنت تستخدم Spyder:

1. افتح ملف:

```text
mt5_direct_pull_diagnostic_v2.py
```

2. من Run Settings أو Configuration per file أضف Arguments مثل:

```text
--days 90
```

أو:

```text
--days 365
```

3. شغل الملف.

لكن لتشغيل Streamlit Dashboard، الأفضل استخدام Command Prompt:

```bash
streamlit run mt5_diagnostic_dashboard.py
```

---

## شرح أهم النتائج

### Summary

يعرض مؤشرات الأداء الأساسية:

- `total_trades` عدد الصفقات
- `wins` عدد الصفقات الرابحة
- `losses` عدد الصفقات الخاسرة
- `win_rate` نسبة الربح
- `net_profit` صافي الربح أو الخسارة
- `profit_factor` جودة الربح مقابل الخسارة
- `avg_win` متوسط الصفقة الرابحة
- `avg_loss` متوسط الصفقة الخاسرة
- `best_trade` أفضل صفقة
- `worst_trade` أسوأ صفقة
- `expectancy` متوسط العائد لكل صفقة
- `max_drawdown` أكبر تراجع تقريبي
- `max_loss_streak` أطول سلسلة خسائر

---

### Scores

يعرض درجات تشخيصية من 100:

#### Overall Trading Health Score

التقييم العام للحساب.

#### Discipline Score

يقيس الانضباط، مثل كثرة التداول والدخول السريع بعد الخسارة.

#### Risk Behavior Score

يقيس السلوك الخطير بعد الخسارة، مثل رفع اللوت أو محاولة التعويض.

#### Performance Quality Score

يقيس جودة الأداء المالي.

#### Data Confidence Score

يقيس قوة الثقة في التحليل حسب عدد الصفقات.

---

### Client Diagnosis

يعطي تشخيصاً مكتوباً للعميل يحتوي على:

- Executive Summary
- Main Problem
- Root Cause Hypothesis
- Data Confidence
- Primary Recommendation

---

### Behavior Flags

يعرض الأخطاء السلوكية المكتشفة، مثل:

#### Overtrading

عدد صفقات مرتفع في يوم واحد.

#### Loss Streak

سلسلة خسائر متتالية.

#### Possible Revenge Trading

رفع حجم الصفقة بعد خسارة.

#### Fast Re-entry After Loss

الدخول بعد خسارة خلال وقت قصير.

---

### Action Plan

خطة تعديل لمدة 7 أيام، تشمل:

- قاعدة التوقف بعد الخسارة
- فترة تهدئة بعد الخسارة
- ثبات حجم الصفقة
- منع كثرة التداول
- فلتر الدخول
- مراجعة أسوأ توقيت أو رمز
- إعادة التحليل

---

## الأخطاء الشائعة وحلولها

### الخطأ: No module named MetaTrader5

الحل:

```bash
python -m pip install MetaTrader5
```

أو:

```bash
python -m pip install -r requirements.txt
```

---

### الخطأ: فشل الاتصال بمنصة MT5

الأسباب المحتملة:

- منصة MT5 غير مفتوحة
- الحساب غير مسجل دخول
- Python لم يجد مسار المنصة
- المنصة مثبتة في مسار مختلف

الحل:

افتح MT5 أولاً، ثم جرب:

```bash
python mt5_direct_pull_diagnostic_v2.py --terminal "C:\Program Files\MetaTrader 5\terminal64.exe" --days 90
```

---

### الخطأ: لم يتم العثور على Deals

الأسباب المحتملة:

- لا توجد صفقات مغلقة في الفترة المحددة
- الحساب المختار ليس الحساب المطلوب
- الفترة قصيرة جداً

الحل:

جرب فترة أطول:

```bash
python mt5_direct_pull_diagnostic_v2.py --days 365
```

أو:

```bash
python mt5_direct_pull_diagnostic_v2.py --from 2025-01-01 --to 2026-06-14
```

---

### الخطأ: streamlit غير معروف

الحل:

```bash
python -m pip install streamlit
```

ثم:

```bash
streamlit run mt5_diagnostic_dashboard.py
```

إذا لم يعمل، جرب:

```bash
python -m streamlit run mt5_diagnostic_dashboard.py
```

---

### Dashboard لا يجد ملف Excel

تأكد أنك شغلت أولاً:

```bash
python mt5_direct_pull_diagnostic_v2.py --days 90
```

ثم شغل:

```bash
streamlit run mt5_diagnostic_dashboard.py
```

إذا كان المجلد في مكان مختلف:

```bash
streamlit run mt5_diagnostic_dashboard.py -- --data-dir "C:\Users\dell\mt5_direct_output_v2"
```

---

## ملاحظات مهمة حول البيانات

هذا المشروع يعتمد على `Deals` من MT5 لأنها تمثل العمليات المنفذة فعلياً.

في MT5 يوجد فرق بين:

- `Orders`: أوامر تم إرسالها وقد تكون منفذة أو غير منفذة
- `Deals`: عمليات تنفيذ فعلية
- `Positions`: مراكز تداول

لتحليل السلوك والنتائج، `Deals` هي الأساس الأفضل.

---

## عدد الصفقات المناسب للتحليل

- أقل من 20 صفقة: قراءة ضعيفة
- 20 إلى 49 صفقة: تشخيص أولي
- 50 إلى 99 صفقة: تشخيص جيد
- 100 صفقة أو أكثر: تشخيص أقوى
- 300 صفقة أو أكثر: مناسب لتحليل سلوكي أعمق

---

## حماية الخصوصية

لا ترفع إلى GitHub:

- ملفات Excel الناتجة من الحسابات
- ملفات CSV الناتجة
- بيانات دخول الحساب
- كلمات المرور
- ملفات تحتوي على معلومات العملاء

تمت إضافة هذه الملفات إلى `.gitignore`:

```text
*.xlsx
*.csv
*.png
*.txt
mt5_direct_output/
mt5_direct_output_v2/
mt5_diagnostic_output/
.env
.streamlit/secrets.toml
```

---

## رفع المشروع إلى GitHub باستخدام GitHub Desktop

1. افتح GitHub Desktop
2. اختر:

```text
File > New Repository
```

3. اسم الريبو المقترح:

```text
mt5-trading-diagnostic
```

4. اضغط:

```text
Create Repository
```

5. انسخ ملفات المشروع داخل مجلد الريبو.
6. ارجع إلى GitHub Desktop.
7. اكتب رسالة Commit:

```text
Initial MT5 trading diagnostic dashboard
```

8. اضغط:

```text
Commit to main
```

9. اضغط:

```text
Publish repository
```

10. اجعل الريبو Private في هذه المرحلة.

---

## أوامر Git لمن يستخدم Terminal

```bash
git init
git add .
git commit -m "Initial MT5 trading diagnostic dashboard"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/mt5-trading-diagnostic.git
git push -u origin main
```

---

## التحذير

هذا المشروع مخصص لتحليل البيانات والتعليم وبناء تقارير تشخيصية.  
لا يقدم توصيات تداول مباشرة.  
التداول يحمل مخاطرة مالية حقيقية، والقرار النهائي مسؤولية المتداول.

---

## Roadmap

أفكار التطوير القادمة:

- إضافة زر داخل Dashboard لسحب البيانات مباشرة من MT5
- اختيار الفترة من داخل الواجهة
- إضافة PDF Report جاهز للعميل
- إضافة Branding خاص بالخدمة
- إضافة تحليل نفسي وسلوكي أعمق
- إضافة Telegram Bot لرفع التقرير أو إرسال ملخص
- إضافة مقارنة بين فترتين
- إضافة فلترة حسب الرمز أو الوقت أو نوع الصفقة
- إضافة Export للنتائج بصيغة تقرير تسويقي للعميل


---

## تشغيل Dashboard V3 مع زر Pull Data

تمت إضافة نسخة جديدة:

```text
mt5_diagnostic_dashboard_v3.py
```

هذه النسخة تسمح لك بسحب بيانات MT5 من داخل Streamlit مباشرة بدون تشغيل سكربت السحب يدوياً.

### تشغيل V3

```bash
streamlit run mt5_diagnostic_dashboard_v3.py
```

من القائمة الجانبية داخل الداشبورد:

1. اختر الفترة:
   - Last N Days
   - Custom Date Range

2. اكتب عدد الأيام أو اختر التاريخ.

3. إذا لم يتعرف Python على MT5 تلقائياً، ضع مسار:

```text
terminal64.exe
```

مثال:

```text
C:\Program Files\MetaTrader 5\terminal64.exe
```

4. اضغط:

```text
Pull Latest MT5 Data
```

بعد نجاح السحب، اضغط:

```text
Refresh Dashboard
```

أو سيتم تحديث البيانات تلقائياً عند إعادة تحميل الصفحة.

### ملاحظة مهمة

يجب أن تكون منصة MT5 مفتوحة ومسجل دخولك إلى الحساب الصحيح قبل الضغط على زر Pull Latest MT5 Data.


---

## Dashboard V4 - File Upload Mode

تمت إضافة نسخة عملية لا تحتاج إلى وجود منصة العميل أو تسجيل الدخول إلى حسابه.

الملفات الجديدة:

```text
mt5_file_analyzer.py
mt5_diagnostic_dashboard_v4_file_upload.py
```

### الفكرة

بدلاً من سحب البيانات من منصة MT5 مباشرة، يقوم العميل بإرسال كشف الحساب بصيغة:

```text
CSV
HTML
XLS
XLSX
```

ثم يتم رفع الملف داخل الداشبورد وتحليله بنفس طريقة V2/V3.

### تشغيل V4

```bash
streamlit run mt5_diagnostic_dashboard_v4_file_upload.py
```

### استخدام V4

1. افتح الداشبورد.
2. من القائمة الجانبية ارفع ملف كشف MT5.
3. اضغط:

```text
Analyze Uploaded File
```

4. سيقوم النظام بإنشاء تقرير وداشبورد كامل من الملف فقط.

### تشغيل التحليل من Command Prompt بدون Streamlit

```bash
python mt5_file_analyzer.py "statement.html"
```

أو:

```bash
python mt5_file_analyzer.py "statement.csv" --output-dir "client_report_output"
```

### المخرجات

```text
mt5_file_output/
├── mt5_file_diagnostic_report_v2.xlsx
├── diagnostic_report_ar_v2.txt
├── raw_uploaded_data.csv
├── trade_deals_clean.csv
├── position_summary.csv
├── scores.csv
├── client_diagnosis.csv
└── action_plan.csv
```

### ملاحظة

هذه النسخة هي الأفضل تجارياً، لأنها تسمح بتحليل حساب العميل بدون الحاجة إلى الوصول إلى جهازه أو منصة MT5 الخاصة به.
