# Mask Trader AI — MT5 Trading Diagnostic

أداة عربية لتحليل كشوف حسابات MetaTrader 5 واكتشاف مشكلات الأداء والانضباط والمخاطر. تستقبل CSV وTXT وHTML وXLS وXLSX، ثم تنشئ Dashboard وتقرير Excel وتقريرًا عربيًا قابلًا للتسليم للعميل.

> الأداة تحليلية وتعليمية، وليست توصية تداول أو وعدًا بتحقيق أرباح.

## ما الذي تحلله؟

- صافي الربح، Win Rate، Profit Factor وExpectancy.
- Max Drawdown بالقيمة والنسبة عند توفر رصيد بداية واضح.
- Overtrading وسلاسل الخسائر.
- الدخول السريع ورفع اللوت بعد الخسارة.
- الصفقات التي لا يظهر فيها وقف خسارة.
- أفضل وأسوأ رمز وساعة ويوم واتجاه.
- درجات الأداء والانضباط وسلوك المخاطرة وثقة البيانات.
- تشخيص عربي وخطة تحسين لمدة سبعة أيام وحلول عملية.

## الخصوصية

- واجهة Streamlit تعالج كل ملف داخل مجلد مؤقت معزول.
- الملف المرفوع والتقارير المؤقتة تُحذف آليًا بعد تحميل النتائج إلى ذاكرة الجلسة.
- لا يظهر للمستخدم خيار كتابة مسار على الخادم.
- الحد الأقصى للرفع 25MB.
- لا تُرفع تقارير العملاء أو ملفات CSV وExcel الناتجة إلى GitHub.

عند تشغيل الخدمة على الإنترنت، يجب إضافة تسجيل دخول ودفع وقاعدة بيانات مشفرة وسياسة احتفاظ قبل فتحها مباشرة للعملاء. النسخة الحالية مناسبة لخدمة Managed Service يديرها فريق Mask Trader AI.

## التشغيل

يتطلب Python 3.10 أو أحدث.

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
python -m pip install -r requirements.txt
streamlit run mt5_diagnostic_dashboard.py
```

macOS/Linux:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run mt5_diagnostic_dashboard.py
```

## التشغيل من سطر الأوامر

```bash
python mt5_file_analyzer.py statement.html --output-dir mt5_file_output
```

## المخرجات

ينشئ المحلل `mt5_file_diagnostic_report_v2.xlsx` و`diagnostic_report_ar_v2.txt`.

ويتضمن Excel: Account Info وSummary وScores وClient Diagnosis وAction Plan وBehavior Flags وSmart Solutions وPosition Summary وTrade Deals وتحليلات الرمز والساعة واليوم والاتجاه.

## Deals وPositions

بعض كشوف MT5 تحتوي صفًا واحدًا لكل صفقة مغلقة، وبعضها يحتوي عدة Deals للمركز نفسه. عند وجود عمود `Position` أو `Position ID` فعلي، تجمع الأداة الـDeals في Position واحدة قبل حساب عدد الصفقات والسلوك، مع إبقاء Deal rows الأصلية في ورقة مستقلة للمراجعة.

## تجربة كاملة دون كشف حقيقي

ارفع الملف `samples/mt5_realistic_deals_demo.csv` من واجهة Streamlit. يحتوي على رصيد افتتاحي و36 Deal موزعة على 18 Position، مع عمولات وSwap وأنماط سلوكية مقصودة لاختبار التشخيص كاملًا. البيانات صناعية بالكامل ولا تخص أي حساب حقيقي.

## الاختبارات

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

تعمل الاختبارات تلقائيًا في GitHub Actions عند فتح Pull Request.

## هيكل المشروع

```text
.
├── mt5_file_analyzer.py
├── mt5_diagnostic_dashboard.py
├── mt5_sample_statement_for_analysis.html
├── requirements.txt
├── requirements-dev.txt
├── tests/
├── docs/
└── .github/workflows/tests.yml
```

## المسار التجاري

راجع [دليل البيع والتسليم](docs/SALES_PLAYBOOK_AR.md) و[سياسة الخصوصية التشغيلية](docs/PRIVACY_AR.md).
