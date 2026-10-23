import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
import os

def generate_report_creation_guide():
    doc = docx.Document()

    # 1. Page Setup (A4, 1-inch margins on all sides)
    for section in doc.sections:
        section.page_width = Inches(8.27)
        section.page_height = Inches(11.69)
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        section.header_distance = Inches(0.5)
        section.footer_distance = Inches(0.5)

    # Colors
    NAVY = RGBColor(0x00, 0x33, 0x4E)      # #00334E (Corporate Primary)
    SLATE = RGBColor(0x1E, 0x29, 0x3B)     # #1E293B (Dark Slate / Headings 2)
    GRAY = RGBColor(0x55, 0x55, 0x55)      # #555555 (Captions, subtitles)
    BLACK = RGBColor(0x11, 0x18, 0x27)     # #111827 (Body text)
    BORDER_COLOR = "CBD5E1"
    BG_COLOR = "F8FAFC"

    def set_cell_background(cell, color_hex):
        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
        cell._tc.get_or_add_tcPr().append(shading)

    def set_cell_margins(cell, top=140, bottom=140, left=180, right=180):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}>'
                          f'<w:top w:w="{top}" w:type="dxa"/>'
                          f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
                          f'<w:left w:w="{left}" w:type="dxa"/>'
                          f'<w:right w:w="{right}" w:type="dxa"/>'
                          f'</w:tcMar>')
        tcPr.append(tcMar)

    def set_cell_borders(cell, color="CBD5E1", sz="6", val="single"):
        tcPr = cell._tc.get_or_add_tcPr()
        borders = parse_xml(f'<w:tcBorders {nsdecls("w")}>'
                            f'<w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
                            f'<w:left w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
                            f'<w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
                            f'<w:right w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
                            f'</w:tcBorders>')
        tcPr.append(borders)

    def add_title(title_text, subtitle_text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(title_text)
        run.bold = True
        run.font.name = "Calibri"
        run.font.size = Pt(20)
        run.font.color.rgb = NAVY

        p_sub = doc.add_paragraph()
        p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_sub.paragraph_format.space_before = Pt(0)
        p_sub.paragraph_format.space_after = Pt(24)
        run_sub = p_sub.add_run(subtitle_text)
        run_sub.italic = True
        run_sub.font.name = "Calibri"
        run_sub.font.size = Pt(12)
        run_sub.font.color.rgb = GRAY

    def add_h1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(8)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.bold = True
        run.font.name = "Calibri"
        run.font.size = Pt(15)
        run.font.color.rgb = NAVY
        return p

    def add_h2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(13)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.bold = True
        run.font.name = "Calibri"
        run.font.size = Pt(13)
        run.font.color.rgb = SLATE
        return p

    def add_p(text, bold_prefix=None):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            r_bold = p.add_run(bold_prefix)
            r_bold.bold = True
            r_bold.font.name = "Calibri"
            r_bold.font.size = Pt(11.5)
            r_bold.font.color.rgb = BLACK
        r_text = p.add_run(text)
        r_text.font.name = "Calibri"
        r_text.font.size = Pt(11.5)
        r_text.font.color.rgb = BLACK
        return p

    def add_bullet(text, bold_prefix=None):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.left_indent = Inches(0.25)
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.15

        r_bullet = p.add_run("•  ")
        r_bullet.font.name = "Calibri"
        r_bullet.font.size = Pt(11.5)
        r_bullet.font.color.rgb = NAVY

        if bold_prefix:
            r_bold = p.add_run(bold_prefix)
            r_bold.bold = True
            r_bold.font.name = "Calibri"
            r_bold.font.size = Pt(11.5)
            r_bold.font.color.rgb = BLACK

        r_text = p.add_run(text)
        r_text.font.name = "Calibri"
        r_text.font.size = Pt(11.5)
        r_text.font.color.rgb = BLACK
        return p

    def add_screenshot(fig_num, title, instruction):
        table = doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.cell(0, 0)
        cell.width = Inches(6.27)
        set_cell_background(cell, BG_COLOR)
        set_cell_margins(cell, top=160, bottom=160, left=200, right=200)
        set_cell_borders(cell, color=BORDER_COLOR, sz="6", val="single")

        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(4)

        r_head = p.add_run(f"[ МЕСТО ДЛЯ СКРИНШОТА {fig_num}: {title} ]\n")
        r_head.bold = True
        r_head.font.name = "Calibri"
        r_head.font.size = Pt(10.5)
        r_head.font.color.rgb = NAVY

        r_desc = p.add_run(f"Что сфотографировать: {instruction}")
        r_desc.italic = True
        r_desc.font.name = "Calibri"
        r_desc.font.size = Pt(9.5)
        r_desc.font.color.rgb = GRAY

        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_before = Pt(4)
        p_cap.paragraph_format.space_after = Pt(12)

        r_fig = p_cap.add_run(f"Рис. {fig_num}. ")
        r_fig.bold = True
        r_fig.italic = True
        r_fig.font.name = "Calibri"
        r_fig.font.size = Pt(10.0)
        r_fig.font.color.rgb = GRAY

        r_title = p_cap.add_run(title)
        r_title.italic = True
        r_title.font.name = "Calibri"
        r_title.font.size = Pt(10.0)
        r_title.font.color.rgb = GRAY

    def add_callout(text, bold_prefix="Важно: "):
        table = doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.cell(0, 0)
        cell.width = Inches(6.27)
        set_cell_background(cell, "F0F9FF")
        set_cell_margins(cell, top=140, bottom=140, left=180, right=180)
        
        tcPr = cell._tc.get_or_add_tcPr()
        borders = parse_xml(f'<w:tcBorders {nsdecls("w")}>'
                            f'<w:top w:val="none"/>'
                            f'<w:left w:val="single" w:sz="24" w:space="0" w:color="00334E"/>'
                            f'<w:bottom w:val="none"/>'
                            f'<w:right w:val="none"/>'
                            f'</w:tcBorders>')
        tcPr.append(borders)

        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.15

        r_bold = p.add_run(bold_prefix)
        r_bold.bold = True
        r_bold.font.name = "Calibri"
        r_bold.font.size = Pt(11.0)
        r_bold.font.color.rgb = NAVY

        r_text = p.add_run(text)
        r_text.font.name = "Calibri"
        r_text.font.size = Pt(11.0)
        r_text.font.color.rgb = BLACK

    # ========================================================
    # DOCUMENT GENERATION
    # ========================================================

    # Header
    add_title("ИНСТРУКЦИЯ ПО СОЗДАНИЮ ОТЧЕТОВ", 
              "Руководство куратора по проектированию форм и запуску сборов (ЦОПП РАС)")

    # ВАЖНОЕ ТРЕБОВАНИЕ БЕЗОПАСНОСТИ (152-ФЗ)
    sec_table = doc.add_table(rows=1, cols=1)
    sec_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    sec_cell = sec_table.cell(0, 0)
    sec_cell.width = Inches(6.27)
    set_cell_background(sec_cell, "FEF2F2")
    set_cell_margins(sec_cell, top=160, bottom=160, left=200, right=200)

    sec_tcPr = sec_cell._tc.get_or_add_tcPr()
    sec_borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:top w:val="single" w:sz="8" w:space="0" w:color="FECACA"/>'
        f'<w:left w:val="single" w:sz="32" w:space="0" w:color="DC2626"/>'
        f'<w:bottom w:val="single" w:sz="8" w:space="0" w:color="FECACA"/>'
        f'<w:right w:val="single" w:sz="8" w:space="0" w:color="FECACA"/>'
        f'</w:tcBorders>'
    )
    sec_tcPr.append(sec_borders)

    p_sec_head = sec_cell.paragraphs[0]
    p_sec_head.paragraph_format.space_before = Pt(2)
    p_sec_head.paragraph_format.space_after = Pt(4)
    r_sh = p_sec_head.add_run("ВАЖНОЕ ТРЕБОВАНИЕ БЕЗОПАСНОСТИ (152-ФЗ):")
    r_sh.bold = True
    r_sh.font.name = "Calibri"
    r_sh.font.size = Pt(11.5)
    r_sh.font.color.rgb = RGBColor(0xDC, 0x26, 0x26)

    p_sec_1 = sec_cell.add_paragraph()
    p_sec_1.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_sec_1.paragraph_format.space_before = Pt(2)
    p_sec_1.paragraph_format.space_after = Pt(4)
    p_sec_1.paragraph_format.line_spacing = 1.15
    r_s1_a = p_sec_1.add_run("В Регионально-аналитической системе ЦОПП ")
    r_s1_a.font.name = "Calibri"
    r_s1_a.font.size = Pt(10.5)
    r_s1_b = p_sec_1.add_run("КАТЕГОРИЧЕСКИ ЗАПРЕЩАЕТСЯ ")
    r_s1_b.bold = True
    r_s1_b.font.name = "Calibri"
    r_s1_b.font.size = Pt(10.5)
    r_s1_b.font.color.rgb = RGBColor(0xDC, 0x26, 0x26)
    r_s1_c = p_sec_1.add_run("сбор любых форм, содержащих персональные данные физических лиц (обучающихся, выпускников, педагогов, родителей).")
    r_s1_c.font.name = "Calibri"
    r_s1_c.font.size = Pt(10.5)

    p_sec_bh = sec_cell.add_paragraph()
    p_sec_bh.paragraph_format.space_before = Pt(2)
    p_sec_bh.paragraph_format.space_after = Pt(2)
    r_sbh = p_sec_bh.add_run("К сбору строго запрещены:")
    r_sbh.bold = True
    r_sbh.font.name = "Calibri"
    r_sbh.font.size = Pt(10.5)
    r_sbh.font.color.rgb = RGBColor(0x11, 0x18, 0x27)

    bullets_sec = [
        "ФИО, паспортные данные, номера СНИЛС и ИНН;",
        "личные контакты (телефоны, email, адреса проживания);",
        "даты рождения и любые сведения, позволяющие идентифицировать конкретного человека."
    ]
    for b_item in bullets_sec:
        pb = sec_cell.add_paragraph()
        pb.paragraph_format.left_indent = Inches(0.2)
        pb.paragraph_format.space_before = Pt(1)
        pb.paragraph_format.space_after = Pt(2)
        pb.paragraph_format.line_spacing = 1.15
        rb_dot = pb.add_run("•  ")
        rb_dot.bold = True
        rb_dot.font.name = "Calibri"
        rb_dot.font.size = Pt(10.5)
        rb_dot.font.color.rgb = RGBColor(0xDC, 0x26, 0x26)
        rb_t = pb.add_run(b_item)
        rb_t.font.name = "Calibri"
        rb_t.font.size = Pt(10.5)
        rb_t.font.color.rgb = RGBColor(0x11, 0x18, 0x27)

    p_sec_2 = sec_cell.add_paragraph()
    p_sec_2.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_sec_2.paragraph_format.space_before = Pt(4)
    p_sec_2.paragraph_format.space_after = Pt(4)
    p_sec_2.paragraph_format.line_spacing = 1.15
    r_s2_a = p_sec_2.add_run("Платформа предназначена ")
    r_s2_a.font.name = "Calibri"
    r_s2_a.font.size = Pt(10.5)
    r_s2_b = p_sec_2.add_run("исключительно для обобщенных статистических данных ")
    r_s2_b.bold = True
    r_s2_b.font.name = "Calibri"
    r_s2_b.font.size = Pt(10.5)
    r_s2_c = p_sec_2.add_run("(численность, проценты, количественные показатели, сведения об инфраструктуре и оборудовании).")
    r_s2_c.font.name = "Calibri"
    r_s2_c.font.size = Pt(10.5)

    p_sec_3 = sec_cell.add_paragraph()
    p_sec_3.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_sec_3.paragraph_format.space_before = Pt(4)
    p_sec_3.paragraph_format.space_after = Pt(2)
    p_sec_3.paragraph_format.line_spacing = 1.15
    r_s3_a = p_sec_3.add_run("Ответственность за соблюдение законодательства возлагается на лицо, формирующее шаблон. ")
    r_s3_a.font.name = "Calibri"
    r_s3_a.font.size = Pt(10.5)
    r_s3_del = p_sec_3.add_run("При выявлении в форме персональных данных отчет и все собранные по нему сведения будут незамедлительно и безвозвратно удалены из системы администратором.")
    r_s3_del.bold = True
    r_s3_del.font.name = "Calibri"
    r_s3_del.font.size = Pt(10.5)
    r_s3_del.font.color.rgb = RGBColor(0xB9, 0x1C, 0x1C)

    # Section 1
    add_h1("1. Архитектура и жизненный цикл отчетов в системе")
    add_p("В Регионально-аналитической системе ЦОПП сбор данных построен на четком разделении эталонных структур и оперативных кампаний сбора:")
    add_bullet("«Шаблон отчета» — эталонная электронная форма (схема). Включает в себя наименование отчета, структуру тематических листов, перечень колонок, типы вводимых данных, подключенные справочники и формулы проверки. Шаблон хранится в реестре «Шаблоны» и не содержит привязки к конкретному дедлайну или списку должников.", bold_prefix="Эталонный шаблон. ")
    add_bullet("«Кампания сбора (Опубликованный отчет)» — конкретный запуск сбора данных на основе выбранного шаблона. При запуске руководитель указывает период сдачи (месяц, квартал, год), фиксирует крайний срок (дедлайн), прикрепляет сопроводительные файлы и назначает учреждения-исполнители.", bold_prefix="Кампания сбора. ")
    add_p("Такая модель позволяет один раз спроектировать идеальную таблицу отчета и затем многократно использовать её для ежемесячных или ежегодных сборов в один клик без повторной верстки.")
    add_callout("Срок сдачи (дедлайн) никогда не устанавливается при проектировании шаблона. Он назначается только в момент запуска сбора за конкретный период, что исключает появление ложных отметок о просрочке у эталонных форм.", bold_prefix="Обратите внимание: ")

    # Section 2
    add_h1("2. Создание отчета с нуля: Визуальный «Конструктор отчетов»")
    add_p("Конструктор отчетов позволяет спроектировать электронную форму любой сложности без привлечения программистов: создавать многостраничные таблицы, настраивать выпадающие списки, подсказки к полям и иерархические («двухэтажные») шапки.")

    add_h2("2.1. Вход в Конструктор и базовые параметры формы")
    add_p("Для начала создания отчета перейдите в модуль «Отчеты» и в правом верхнем углу нажмите кнопку «+ Создать новый отчёт». Откроется интерфейс Конструктора.")
    add_p("В верхнем блоке заполните базовые реквизиты формы:")
    add_bullet("«Короткое имя отчета» — лаконичное наименование для карточек в реестрах, системных фильтров и экспорта (например: «Мониторинг ПК 2026», «Трудоустройство выпускников 9 классов»).", bold_prefix="Краткое наименование. ")
    add_bullet("«Полное имя отчета» — официальное наименование документа в соответствии с приказом или распоряжением. Данный заголовок отображается в шапке электронной формы при ее заполнении учреждениями.", bold_prefix="Полное наименование. ")
    add_bullet("«Период отчета» — выберите базовый тип отчетного интервала (учебный год, полугодие, квартал, месяц или точный диапазон дат).", bold_prefix="Тип периода. ")

    add_screenshot(1, "Форма ввода наименований и периода в Конструкторе",
                   "Верхняя часть страницы Конструктора: поля «Короткое имя отчета», «Полное имя отчета» и селектор периода.")

    add_h2("2.2. Назначение групп доступа и прикрепление документов")
    add_p("Ниже расположен блок предварительного назначения прав и добавления сопутствующих файлов:")
    add_bullet("«Назначить целой группе» — отметьте чекбоксами целевые категории учреждений, которым предназначается отчет (например: «СПО», «Школы», «Вузы»). Для выбора всех зарегистрированных организаций воспользуйтесь кнопкой «Выбрать всех / Снять выделение».", bold_prefix="Группы учреждений. ")
    add_bullet("«Прикрепленные файлы» — если сбор регламентирован официальным письмом Министерства или имеет методические указания, нажмите «Выбрать из уже загруженных» (для выбора файла из общего репозитория системы) либо «Загрузить с ПК» (поддерживаются форматы .pdf, .docx, .xlsx). Прикрепленные документы будут доступны учреждениям для скачивания прямо из карточки отчета.", bold_prefix="Сопроводительные документы. ")

    add_screenshot(2, "Блок выбора групп доступа и прикрепления файлов",
                   "Блок «Предварительное назначение прав доступа» с чекбоксами групп («СПО», «Школы») и кнопками выбора/загрузки файлов.")

    add_h2("2.3. Создание тематических листов (разделов) отчета")
    add_p("Сложные формы отчетов рекомендуется разделять на несколько вкладок (листов), аналогично вкладкам в Excel. Это существенно упрощает заполнение для организаций.")
    add_bullet("В блоке «Структура отчета» введите название раздела в поле «Название листа» (например: «Общие сведения», «Трудоустройство», «Материальная база») и нажмите кнопку «Добавить лист».", bold_prefix="Добавление листа. ")
    add_bullet("«Группы доступа листа» — в заголовке каждого листа расположена кнопка настройки целевых групп. Вы можете настроить форму так, чтобы первый лист заполняли все организации, а второй лист — только колледжи и техникумы (СПО).", bold_prefix="Разделение доступа по листам. ")
    add_bullet("«Разрешить добавление строк» — включите данный переключатель, если таблица предполагает внесение переменного числа строк (например, перечень закупленного оборудования, список предприятий-партнеров). В форме у учреждения появится кнопка «+ Добавить строку».", bold_prefix="Динамические таблицы. ")

    add_screenshot(3, "Панель листа отчета с настройками доступа и добавления строк",
                   "Карточка созданного листа в Конструкторе с полем названия, кнопкой групп доступа и тумблером «Разрешить добавление строк».")

    add_h2("2.4. Добавление и настройка колонок (показателей) таблицы")
    add_p("В нижней части карточки каждого листа расположена панель добавления столбцов таблицы:")
    add_bullet("«Заголовок столбца» — введите точное наименование графы (например: «Всего выпускников», «Специальность по диплому», «Трудоустроено на предприятия ОПК»).", bold_prefix="Заголовок показателя. ")
    add_bullet("«Тип поля» — выберите формат вводимой информации:", bold_prefix="Тип данных. ")
    add_bullet("Числовое — принимает только числа, автоматически участвует в расчете итоговых сумм, проверках равенств и аналитических срезах;", bold_prefix="  - ")
    add_bullet("Текстовое — строковое поле для произвольного текстового ввода (ФИО, комментарии, адреса);", bold_prefix="  - ")
    add_bullet("Выпадающий список — поле со строгим выбором из справочника вариантов. При выборе этого типа отображается селектор для выбора шаблона списка из модуля «Шаблоны списков» (например: «Перечень специальностей СПО», «Муниципалитеты области»). Использование выпадающих списков исключает опечатки со стороны учреждений.", bold_prefix="  - ")
    add_bullet("«Обязательно» — при включении чекбокса система заблокирует сдачу отчета, если организация оставит данное поле пустым.", bold_prefix="Обязательность заполнения. ")
    add_bullet("«Множественное» — позволяет пользователю вносить несколько значений в одну графу (появляется кнопка «+ Добавить еще»).", bold_prefix="Множественные значения. ")
    add_bullet("«Подсказка (необязательно)» — подробное разъяснение правил заполнения графы. В форме у учреждения рядом с названием поля отобразится вопросительный знак «?», при наведении на который появится ваш текст подсказки.", bold_prefix="Контекстная подсказка. ")
    add_p("После настройки параметров нажмите синюю кнопку «Добавить». Показатель отобразится в табличной структуре листа.")

    add_screenshot(4, "Форма добавления поля в лист Конструктора",
                   "Нижняя панель листа: поле заголовка, выбор типа (Числовое/Текстовое/Выпадающий список), чекбокс «Обязательно», поле подсказки и кнопка «Добавить».")

    add_h2("2.5. Построение многоуровневых шапок («из них:») и управление структурой")
    add_p("Многие формы регионального мониторинга требуют создания сложных «двухэтажных» шапок, когда один показатель детализируется подкатегориями (например: общая колонка «Численность выпускников», а под ней подколонки «из них: очная форма», «заочная форма»).")
    add_bullet("В карточке каждого добавленного поля расположены стрелки регулировки уровня: стрелка вправо (→) понижает уровень поля, превращая его в подраздел предыдущего («из них:»); стрелка влево (←) возвращает поле на верхний уровень.", bold_prefix="Смещение уровней вложенности. ")
    add_bullet("Конструктор автоматически формирует сквозную нумерацию граф (1., 1.1., 1.2., 2. и т.д.), полностью соответствующую стандартам статистической отчетности.", bold_prefix="Иерархическая нумерация. ")
    add_bullet("Для числовых иерархий система автоматически контролирует логику данных: сумма дочерних показателей не может превышать значение родительской строки.", bold_prefix="Автоматический контроль сумм. ")
    add_bullet("Порядок граф легко меняется простым перетаскиванием мыши за маркер «⠿» (Drag-and-Drop). Также доступна кнопка вставки нового поля в произвольное место таблицы.", bold_prefix="Изменение порядка полей. ")

    add_screenshot(5, "Иерархическая структура полей со смещением уровней вложенности",
                   "Список полей в Конструкторе с отображением родительских и дочерних граф («из них:»), стрелками уровня и рассчитанной нумерацией.")

    add_h2("2.6. Предпросмотр и сохранение шаблона")
    add_p("Перед завершением работы настоятельно рекомендуется проверить форму:")
    add_bullet("В правом верхнем углу Конструктора нажмите кнопку «Предпросмотр». Откроется интерактивное модальное окно с точной копией формы отчета — проверьте корректность вкладок листов, колонок, подсказок «?» и выпадающих списков.", bold_prefix="Интерактивный предпросмотр. ")
    add_bullet("Убедившись в правильности структуры, нажмите кнопку «Сохранить шаблон» в самом низу страницы. Созданный шаблон будет зафиксирован в базе данных и появится в реестре во вкладке «Шаблоны».", bold_prefix="Сохранение в реестр. ")

    add_screenshot(6, "Окно интерактивного предпросмотра формы отчета",
                   "Модальное окно предпросмотра созданной формы со всеми вкладками листов, полями таблицы и кнопкой закрытия.")

    # Section 3
    add_h1("3. Быстрое создание отчета импортом из файла Excel")
    add_p("Если таблица отчета уже составлена в Excel, вам не требуется вносить десятки граф вручную. Система оснащена интеллектуальным модулем автоматического парсинга.")

    add_h2("3.1. Порядок загрузки файла Excel")
    add_p("Для автоматического создания отчета из существующей таблицы:")
    add_bullet("В модуле «Отчеты» на верхней панели нажмите зеленую кнопку «Создать из Excel».", bold_prefix="1. Вызов импорта. ")
    add_bullet("В открывшемся окне нажмите «Выберите файл» и укажите нужный документ на вашем ПК (поддерживаются файлы форматов .xlsx и .xls).", bold_prefix="2. Выбор файла. ")
    add_bullet("Нажмите кнопку «Загрузить и создать».", bold_prefix="3. Запуск парсинга. ")
    add_p("Система автоматически прочитает все листы книги Excel, проанализирует объединенные ячейки заголовков (colspan/rowspan), сформирует структуру иерархических шапок, определит типы колонок и создаст черновой шаблон, после чего автоматически перенаправит вас в Конструктор для финальной сверки.")

    add_screenshot(7, "Модальное окно «Создать отчет из Excel»",
                   "Окно загрузки файла Excel с полем выбора файла, предупреждением о ручной проверке и кнопкой «Загрузить и создать».")

    add_h2("3.2. Доработка импортированной формы в Конструкторе")
    add_p("После завершения импорта откроется Конструктор с полностью собранной таблицей. Выполните обязательную контрольную проверку:")
    add_bullet("Сверьте наименования листов и заголовки столбцов;", bold_prefix="• ")
    add_bullet("Убедитесь, что для числовых граф установлен тип «Числовое», а для текстовых — «Текстовое» (при необходимости подключите нужные справочники из выпадающих списков);", bold_prefix="• ")
    add_bullet("Задайте короткое и полное наименование отчета, укажите группы доступа учреждений и нажмите «Сохранить изменения».", bold_prefix="• ")

    add_screenshot(8, "Проверка распознанной структуры Excel в Конструкторе",
                   "Экран Конструктора сразу после импорта Excel-файла с автоматически заполненными листами и столбцами таблицы.")

    # Section 4
    add_h1("4. Запуск сбора отчета (Публикация кампании из Шаблона)")
    add_p("Созданный шаблон хранится в реестре вкладки «Шаблоны». Чтобы открыть сбор сведений для подведомственных учреждений, куратор запускает кампанию сбора.")

    add_h2("4.1. Пошаговый запуск кампании из карточки шаблона")
    add_bullet("Перейдите в субвкладку «Шаблоны» модуля «Отчеты».", bold_prefix="Шаг 1. ")
    add_bullet("Найдите карточку нужного отчета и нажмите в ее нижней части кнопку «Запустить сбор» (также доступен пункт «Запустить новый период» в меню трех точек «...»).", bold_prefix="Шаг 2. ")
    add_bullet("В открывшемся модальном окне «Запуск нового периода» на вкладке «Основные настройки» укажите параметры текущей кампании:", bold_prefix="Шаг 3. ")
    add_bullet("Краткое и полное наименование (при необходимости скорректируйте формулировку);", bold_prefix="  - ")
    add_bullet("Новый период — выберите точный интервал сдачи (например: «Сентябрь 2026», «1 полугодие 2026/2027 учебного года»);", bold_prefix="  - ")
    add_bullet("Новый дедлайн — установите крайний срок сдачи (дату, после наступления которой форма автоматически заблокируется);", bold_prefix="  - ")
    add_bullet("Прикрепленные файлы — отметьте чекбоксами официальные письма и инструкции, сопровождающие данный сбор.", bold_prefix="  - ")

    add_screenshot(9, "Карточка шаблона с кнопками управления",
                   "Карточка шаблона во вкладке «Шаблоны» с кнопками «Запустить сбор», «Сводные данные» и «Конструктор».")

    add_screenshot(10, "Модальное окно «Запуск нового периода» (Основные настройки)",
                   "Окно запуска сбора: поля наименований, селектор периода, поле выбора даты дедлайна и список прикрепляемых файлов.")

    add_h2("4.2. Выборочное включение показателей («Управление полями»)")
    add_p("Если в эталонном шаблоне заложено 20 показателей, но в конкретном месяце требуется собрать только 5 из них:")
    add_bullet("В модальном окне запуска сбора перейдите на вкладку «Управление полями».", bold_prefix="1. Переход во вкладку. ")
    add_bullet("Выключите тумблеры напротив тех граф, сбор по которым в данном периоде не проводится.", bold_prefix="2. Отключение граф. ")
    add_p("В сводной таблице для отключенных граф будет автоматически выведено обозначение «Сбор завершен», а учреждению не придется тратить время на ввод ненужных цифр.")

    add_screenshot(11, "Вкладка «Управление полями» в окне запуска сбора",
                   "Вкладка «Управление полями» с переключателями (тумблерами) активности граф по каждому листу отчета.")

    add_h2("4.3. Публикация формы")
    add_p("В нижней панели окна выберите целевое действие:")
    add_bullet("«Опубликовать сразу» — сбор открывается немедленно. Отчет появляется в личных кабинетах назначенных организаций в блоке «Активные отчеты», а на карточке запускается таймер дедлайна.", bold_prefix="Опубликовать. ")
    add_bullet("«Сохранить как Черновик» — отчет сохраняется во вкладке «Черновики» без открытия доступа учреждениям. Это позволяет заранее подготовить кампанию и открыть ее позже.", bold_prefix="В черновики. ")

    # Section 5
    add_h1("5. Назначение исполнителей и оперативное управление отчетом")

    add_h2("5.1. Управление списком назначенных организаций")
    add_p("Куратор может в любой момент скорректировать перечень учреждений, обязанных сдать отчет:")
    add_bullet("На карточке отчета нажмите кнопку действий (три точки «...») в правом верхнем углу и выберите «Назначить исполнителей».", bold_prefix="1. Открытие доступа. ")
    add_bullet("В модальном окне воспользуйтесь инструментами быстрого подбора:", bold_prefix="2. Настройка списка. ")
    add_bullet("Поисковая строка — моментальная фильтрация по наименованию или номеру учреждения;", bold_prefix="  - ")
    add_bullet("Кнопки категорий — назначение отчета всем организациям выбранного типа («СПО», «Школы») в один клик;", bold_prefix="  - ")
    add_bullet("Чекбокс «Показать только назначенных» — скрывает сторонние организации, позволяя проверить текущий список;", bold_prefix="  - ")
    add_bullet("Счетчик выбранных («X выбрано») — наглядно отображает итоговое количество организаций.", bold_prefix="  - ")
    add_bullet("Нажмите кнопку «Сохранить доступ». Назначенные учреждения мгновенно увидят форму в своих личных кабинетах.", bold_prefix="3. Сохранение. ")

    add_screenshot(12, "Модальное окно назначения организаций-исполнителей",
                   "Окно «Назначить исполнителей»: строка поиска, кнопки групп, список учреждений с чекбоксами и счетчик выбранных организаций.")

    add_h2("5.2. Корректировка параметров и управление статусом кампании")
    add_p("Через контекстное меню карточки отчета (три точки «...») куратору доступны регламентные действия:")
    add_bullet("«Изменить настройки» — продление даты дедлайна, уточнение наименования или прикрепление дополнительного распоряжения;", bold_prefix="Продление сроков: ")
    add_bullet("«Снять с публикации» — временный возврат отчета в черновики (учреждения перестают видеть форму);", bold_prefix="Приостановка: ")
    add_bullet("«Завершить сбор» — досрочная фиксация итогов сбора и перевод формы в режим «Только чтение» для всех организаций;", bold_prefix="Завершение: ")
    add_bullet("«В архив» — перемещение завершенного отчета в архивный реестр для долговременного хранения.", bold_prefix="Архивация: ")

    add_screenshot(13, "Контекстное меню дополнительных действий карточки отчета",
                   "Раскрытое меню трех точек на карточке отчета с пунктами «Назначить исполнителей», «Изменить настройки», «Завершить сбор», «В архив».")

    # Section 6
    add_h1("6. Предварительный просмотр структуры сводной таблицы данных")
    add_p("Чтобы убедиться, как будет выглядеть итоговая сводная ведомость после сбора ответов со всех учреждений, куратор может открыть сводную таблицу еще до начала сбора данных:")
    add_bullet("На карточке шаблона (во вкладке «Шаблоны») либо на карточке опубликованного отчета нажмите кнопку «Сводные данные».", bold_prefix="1. Открытие таблицы. ")
    add_bullet("В новой вкладке браузера откроется полноэкранная таблица с полной структурой: вкладки-листы, иерархическая шапка, перечень колонок и панель инструментов.", bold_prefix="2. Сверка структуры. ")
    add_p("Если сбор уже запущен и организации начали сдавать отчеты, в этой же сводной таблице отображаются их данные с возможностью проверки, inline-редактирования ячеек куратором и выгрузки всей сводки в файл Excel (.xlsx).")

    add_screenshot(14, "Сводная аналитическая таблица данных по отчету",
                   "Полноэкранный вид сводной таблицы данных с вкладками листов, шапкой показателей и кнопками экспорта.")

    # Section 7
    add_h1("7. Чек-лист куратора: Регламент создания и запуска отчета")
    add_p("Для исключения ошибок при подготовке мониторинга рекомендуется следовать пошаговому регламентному чек-листу:")

    # Table
    table = doc.add_table(rows=8, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    col_widths = [Inches(1.2), Inches(3.2), Inches(1.87)]
    for row in table.rows:
        for idx, width in enumerate(col_widths):
            row.cells[idx].width = width

    headers = ["Этап", "Действие куратора", "Результат"]
    hdr_row = table.rows[0]
    for idx, text in enumerate(headers):
        cell = hdr_row.cells[idx]
        set_cell_background(cell, "00334E")
        set_cell_margins(cell, top=140, bottom=140, left=160, right=160)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        run.bold = True
        run.font.name = "Calibri"
        run.font.size = Pt(10.5)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    steps = [
        ("1. Проектирование формы",
         "Создание структуры в Конструкторе с нуля либо импорт существующего файла Excel (.xlsx) через кнопку «Создать из Excel».",
         "Сформирована сетка листов и колонок"),
        ("2. Настройка показателей",
         "Указание типов граф (числа, текст, выпадающие списки), добавление подсказок «?», построение уровней «из них:».",
         "Таблица готова к приему данных"),
        ("3. Фиксация шаблона",
         "Проверка формы в режиме «Предпросмотр» и нажатие кнопки «Сохранить шаблон» в Конструкторе.",
         "Шаблон сохранен в субвкладке «Шаблоны»"),
        ("4. Запуск кампании",
         "Нажатие кнопки «Запустить сбор» на карточке шаблона, выбор отчетного периода и назначение даты дедлайна.",
         "Кампания сбора сконфигурирована"),
        ("5. Прикрепление файлов",
         "Выбор официальных писем, приказов или методических указаний из репозитория для передачи учреждениям.",
         "Документы привязаны к карточке сбора"),
        ("6. Назначение доступа",
         "Выбор целевых категорий («СПО», «Школы») либо конкретных учреждений через меню «Назначить исполнителей».",
         "Отчет отображается в личных кабинетах организаций"),
        ("7. Мониторинг и контроль",
         "Контроль прогресс-бара сдачи на вкладке «Опубликованные», работа со списком должников и проверка ответов.",
         "Своевременный сбор региональных сведений")
    ]

    for row_idx, data in enumerate(steps, start=1):
        row = table.rows[row_idx]
        bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, text in enumerate(data):
            cell = row.cells[col_idx]
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=100, bottom=100, left=140, right=140)
            set_cell_borders(cell, color="E2E8F0", sz="4", val="single")
            p = cell.paragraphs[0]
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            if col_idx == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = p.add_run(text)
                run.bold = True
                run.font.name = "Calibri"
                run.font.size = Pt(10.0)
                run.font.color.rgb = NAVY
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                run = p.add_run(text)
                run.font.name = "Calibri"
                run.font.size = Pt(10.0)
                run.font.color.rgb = BLACK

    # Output path
    output_path = r"c:\Users\abrag\Documents\copp-ras\создание отчетов v2.docx"
    doc.save(output_path)
    print(f"Document saved successfully to {output_path}!")

if __name__ == "__main__":
    generate_report_creation_guide()
