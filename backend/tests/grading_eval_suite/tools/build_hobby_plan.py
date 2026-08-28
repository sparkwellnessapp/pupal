# -*- coding: utf-8 -*-
"""
V5-B plan builder — authors plans/hobby_tvshow.plan.json from the RUBRIC
CONTRACT TEXT ONLY, validates it with the real plan_validator against the real
contract, and renders the human-readable Hebrew review document for the H-4
owner gate.

Authoring rules applied (mission §5 V5-B + K2_FORENSICS §3):
  * where the rubric itemizes components with points, the checks ARE that
    itemization, verbatim points;
  * where the rubric names a deduction («להוריד X»), it becomes kind=tariff
    with exactly that amount;
  * «לא להוריד, לכתוב הערה» becomes kind=note_only;
  * «רק פעם אחת» becomes a charge_group;
  * compound requirements split along the rubric's own nouns (the K2 lesson:
    q1.ב.c4 splits creation vs correct-cell);
  * every check carries rubric_quote — the span it derives from. A check that
    cannot cite a rubric span does not get authored.
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.agents.grader.plan_schemas import GradingPlan, PlanCheck, TerminalPlan
from app.agents.grader.plan_validator import validate_plan
from tests.grading_eval_suite.fixtures import load_bundle

SUITE = Path(__file__).resolve().parents[1]
D = Decimal


def R(cid, pts, he, quote, equiv=None, frac="0.5"):
    return PlanCheck(check_id=cid, description_he=he, kind="required",
                     points=D(str(pts)), partial_fraction=D(frac),
                     equivalence_note=equiv, rubric_quote=quote)


def T(cid, amount, he, quote, group=None):
    return PlanCheck(check_id=cid, description_he=he, kind="tariff",
                     points=D("0"), tariff_amount=D(str(amount)),
                     charge_group=group, rubric_quote=quote)


def N(cid, he, quote):
    return PlanCheck(check_id=cid, description_he=he, kind="note_only",
                     points=D("0"), rubric_quote=quote)


def TP(tid, pts, checks):
    return TerminalPlan(terminal_id=tid, points_possible=D(str(pts)), checks=checks)


TERMINALS = [
    # ── q1.א — מחלקת Hobby ──────────────────────────────────────────────────
    TP("q1.א.c0", 4, [
        R("q1.א.c0.k1", 1, "כותרת מחלקה בשם Hobby",
          "סעיף א: כותרת ותכונות המחלקה Hobby"),
        R("q1.א.c0.k2", 3,
          "שלוש תכונות המחלקה מוגדרות בטיפוסים הנכונים: hobbyName מחרוזת, "
          "isSportive בוליאני, minutes מספר שלם",
          "סעיף א: כותרת ותכונות המחלקה Hobby",
          equiv="שמות תואמי הפתרון לדוגמה (למשל durationInMinutes) תקפים"),
    ]),
    # [A-1, owner H-4 2026-08-28] 2+2 -> 1+1+1+1: the per-parameter split makes
    # dan's ratified 3.5 reachable (1+1+1+0.5)
    TP("q1.א.c1", 4, [
        R("q1.א.c1.k1", 1,
          "חתימת פעולה בונה: public Hobby(string hobbyName, bool isSportive, int minutes)",
          "סעיף א: פעולה בונה Hobby(string hobbyName, bool isSportive, int minutes)"),
        R("q1.א.c1.k2", 1,
          "גוף הבונה משים את הפרמטר hobbyName לתכונה המתאימה",
          "פעולה הבונה תחביב, מקבלת את כל הפרמטרים וקובעת את ערכי התכונות בהתאם"),
        R("q1.א.c1.k3", 1,
          "גוף הבונה משים את הפרמטר isSportive לתכונה המתאימה",
          "פעולה הבונה תחביב, מקבלת את כל הפרמטרים וקובעת את ערכי התכונות בהתאם"),
        R("q1.א.c1.k4", 1,
          "גוף הבונה משים את הפרמטר minutes לתכונה המתאימה",
          "פעולה הבונה תחביב, מקבלת את כל הפרמטרים וקובעת את ערכי התכונות בהתאם",
          equiv="בדיקת טווח על minutes אופציונלית — הפתרון לדוגמה מציין «אם לא בדקתם טווח גם בסדר»"),
    ]),
    # ── q1.ב — PopulateHobbies ──────────────────────────────────────────────
    TP("q1.ב.c0", 2, [
        R("q1.ב.c0.k1", 1, "פעולה פנימית בשם PopulateHobbies מוגדרת במחלקה",
          "כותרת הפעולה + טיפוס מוחזר bool"),
        R("q1.ב.c0.k2", 1, "טיפוס מוחזר bool",
          "כותרת הפעולה + טיפוס מוחזר bool"),
    ]),
    TP("q1.ב.c1", 1, [
        R("q1.ב.c1.k1", 1,
          "לפני הלולאה: בדיקה אם המערך מלא והחזרת false במקרה זה",
          "לפני הלולאה - לבדוק אם המערך מלא, להחזיר false"),
    ]),
    TP("q1.ב.c2", 3, [
        R("q1.ב.c2.k1", 1.5,
          "לולאת קליטה שתנאי ההמשך שלה כולל קיום מקום פנוי במערך "
          "(countHobbies קטן מ-length)",
          "לולאה עד שאין מקום במערך (כל עוד countHobbies קטן מ-length)"),
        R("q1.ב.c2.k2", 1.5,
          "תנאי ההמשך כולל את רצון המשתמש — כל עוד המשתמש עונה Y או y",
          "או כל עוד המשתמש יענה Y או y לשאלה",
          equiv="do-while / דגל בוליאני / break שקולים כשההתנהגות זהה"),
    ]),
    TP("q1.ב.c3", 3, [
        R("q1.ב.c3.k1", 1, "בתוך הלולאה: קליטת שם התחביב",
          "קליטה של 3 נתוני התחביב (name, isSportive, minutes)",
          equiv="[A-5/PL-2] קיצור cw/CR מתקבל כקליטה מוקלדת; המרה מפורשת אינה נדרשת"),
        R("q1.ב.c3.k2", 1, "בתוך הלולאה: קליטת isSportive",
          "קליטה של 3 נתוני התחביב (name, isSportive, minutes)",
          equiv="[A-5/PL-2] קיצור cw/CR מתקבל כקליטה מוקלדת; המרה מפורשת אינה נדרשת"),
        R("q1.ב.c3.k3", 1, "בתוך הלולאה: קליטת minutes",
          "קליטה של 3 נתוני התחביב (name, isSportive, minutes)",
          equiv="[A-5/PL-2] קיצור cw/CR מתקבל כקליטה מוקלדת; המרה מפורשת אינה נדרשת"),
    ]),
    # the K2_FORENSICS case-1 terminal: creation vs correct-cell SPLIT
    TP("q1.ב.c4", 3, [
        R("q1.ב.c4.k1", 1.5,
          "יצירת עצם חדש מטיפוס Hobby עם שלושת הנתונים שנקלטו",
          "יצירה של עצם חדש מטיפוס Hobby"),
        R("q1.ב.c4.k2", 1.5,
          "ההשמה מכניסה את העצם לתא הפנוי המתאים — hobbies[countHobbies] — "
          "כך שהתחביב אכן נוסף למערך ואינו דורס תחביב קיים (יש לעקוב אחר "
          "התנהגות התנאים סביב ההשמה, לא רק אחר צורת השורה)",
          "בתא המתאים במערך (hobbies[countHobbies])"),
    ]),
    TP("q1.ב.c5", 1, [
        R("q1.ב.c5.k1", 1, "בתוך הלולאה: קידום countHobbies",
          "בתוך הלולאה קידום countHobbies"),
    ]),
    TP("q1.ב.c6", 2, [
        R("q1.ב.c6.k1", 1,
          "לפני שאלת ההמשך: בדיקה שעדיין יש מקום במערך",
          "בדיקה אם עדיין יש מקום ושאלה למשתמש — אם הציגו את ההודעה בלי לבדוק "
          "האם יש עדיין מקום להוריד 1"),
        R("q1.ב.c6.k2", 1,
          "שאלה למשתמש האם להמשיך + קליטת התשובה",
          "שאלה למשתמש האם להמשיך + קליטת תשובה"),
    ]),
    TP("q1.ב.c7", 1, [
        R("q1.ב.c7.k1", 1, "מחוץ ללולאה: החזרת true",
          "מחוץ ללולאה - להחזיר ערך true",
          equiv="[A-3/PL-8] החזרת דגל-הצלחה סמנטי (למשל addedAtLeastOne) שקולה — "
                "הפתרון לדוגמה עצמו מחזיר כך"),
    ]),
    # ── q1.ג — PrintAverages ────────────────────────────────────────────────
    TP("q1.ג.c0", 1, [
        R("q1.ג.c0.k1", 1, "כותרת פעולה פנימית PrintAverages עם טיפוס void",
          "כותרת הפעולה + void"),
    ]),
    TP("q1.ג.c1", 1, [
        R("q1.ג.c1.k1", 0.5, "מונה לחוגים הספורטיביים + אתחול ב-0",
          "יצירת 2 מונה … + אתחולם ב-0 (0.5 כ\"א)"),
        R("q1.ג.c1.k2", 0.5, "מונה לחוגים הלא-ספורטיביים + אתחול ב-0",
          "יצירת 2 מונה … + אתחולם ב-0 (0.5 כ\"א)"),
    ]),
    TP("q1.ג.c2", 1, [
        R("q1.ג.c2.k1", 0.5, "צובר דקות לחוגים הספורטיביים + אתחול ב-0",
          "יצירת 2 צוברים … + אתחולם ב-0 (0.5 כ\"א)"),
        R("q1.ג.c2.k2", 0.5, "צובר דקות לחוגים הלא-ספורטיביים + אתחול ב-0",
          "יצירת 2 צוברים … + אתחולם ב-0 (0.5 כ\"א)"),
    ]),
    TP("q1.ג.c3", 3, [
        R("q1.ג.c3.k1", 3,
          "לולאה על מערך התחביבים בגבולות נכונים",
          "לולאה על מערך התחביבים מ-0 עד countHobbies או עד hobbies.length",
          equiv="שתי הצורות ברובריקה שקולות: עד countHobbies, או עד length עם בדיקת null"),
        T("q1.ג.c3.k2", 1,
          "אם הלולאה רצה עד length — קיימת בתוכה בדיקת hobbies[i]!=null "
          "(לולאה עד countHobbies מקיימת את הדרישה ללא בדיקה)",
          "אם עשו לולאה עד length ולא בדקו בפנים שהתא שונה מ-null להוריד 1"),
    ]),
    TP("q1.ג.c4", 3, [
        R("q1.ג.c4.k1", 1, "בתוך הלולאה: בדיקה אם החוג הנוכחי ספורטיבי",
          "בדיקת האם החוג הנוכחי ספורטיבי (1)"),
        R("q1.ג.c4.k2", 1, "צבירת הדקות של חוג ספורטיבי לצובר המתאים",
          "+ צבירה של הדקות שלו (1)"),
        R("q1.ג.c4.k3", 1, "קידום מונה הספורטיביים",
          "+ קידום המונה שלו (1 כ\"א)"),
    ]),
    TP("q1.ג.c5", 3, [
        R("q1.ג.c5.k1", 1, "ענף else / תנאי לחוג לא-ספורטיבי",
          "אם החוג הנוכחי לא ספורטיבי (else) (1)"),
        R("q1.ג.c5.k2", 1, "צבירת הדקות לצובר הלא-ספורטיבי",
          "+ צבירה של הדקות שלו (1)"),
        R("q1.ג.c5.k3", 1, "קידום מונה הלא-ספורטיביים",
          "+ קידום המונה שלו (1)"),
    ]),
    TP("q1.ג.c6", 2, [
        R("q1.ג.c6.k1", 1,
          "בדיקה שמונה הספורטיביים שונה מאפס לפני החלוקה",
          "בדיקה האם המונה … שונה מאפס (1) אם לא מנעו חלוקה באפס להוריד 1"),
        R("q1.ג.c6.k2", 1,
          "חישוב ממוצע הספורטיביים והדפסתו — חישוב שגוי אינו פוגע בבדיקה זו (met; "
          "הוא מחויב בניכוי הנפרד); partially_met שמור למקרה שרכיב שלם — חישוב או "
          "הדפסה — נעדר או שהמיקום שגוי [A-6]",
          "חישוב הממוצע והדפסה (1)"),
        T("q1.ג.c6.k3", 0.5,
          "החישוב המתמטי של הממוצע נכון (כאן, ורק כאן, מחויב חישוב שגוי) [A-6]",
          "אם טעו בחישוב מתמטי להוריד 0.5"),
        T("q1.ג.c6.k4", 0.5,
          "קיימת המרה לממשי בחישוב הממוצע (חלוקה שלמה אינה מספיקה)",
          "אם לא המירו לממשי בחישוב הממוצע להוריד 0.5 (רק פעם אחת)",
          group="q1g-cast-once"),
    ]),
    TP("q1.ג.c7", 2, [
        R("q1.ג.c7.k1", 1,
          "בדיקה שמונה הלא-ספורטיביים שונה מאפס לפני החלוקה",
          "בדיקה האם המונה של … הלא-הספורטיבים שונה מאפס (1)"),
        R("q1.ג.c7.k2", 1,
          "חישוב ממוצע הלא-ספורטיביים והדפסתו — חישוב שגוי אינו פוגע בבדיקה זו "
          "(met; הוא מחויב בניכוי הנפרד); partially_met שמור למקרה שרכיב שלם — "
          "חישוב או הדפסה — נעדר או שהמיקום שגוי [A-6]",
          "חישוב הממוצע והדפסה (1)"),
        T("q1.ג.c7.k3", 0.5,
          "החישוב המתמטי של הממוצע נכון (כאן, ורק כאן, מחויב חישוב שגוי) [A-6]",
          "אם טעו בחישוב מתמטי להוריד 0.5"),
        T("q1.ג.c7.k4", 0.5,
          "קיימת המרה לממשי בחישוב הממוצע",
          "אם לא המירו לממשי … להוריד 0.5 (רק פעם אחת)",
          group="q1g-cast-once"),
    ]),
    # ── q2.א — TvShow constructor + UpdateRate ─────────────────────────────
    TP("q2.א.c0", 5, [
        R("q2.א.c0.k1", 1, "חתימת פעולה בונה: public TvShow(string name, int channel)",
          "פעולה בונה public TvShow (string name, int channel)"),
        R("q2.א.c0.k2", 2, "השמת name ו-chl מהפרמטרים",
          "פעולה הבונה תוכנית טלוויזיה ששמה name והיא משודרת בערוץ channel"),
        R("q2.א.c0.k3", 2, "קביעת rate=0 ו-isOn=true",
          "קובעת את rate להיות אפס (0) ואת isOn להיות אמת (true)"),
    ]),
    TP("q2.א.c1", 10, [
        R("q2.א.c1.k1", 2, "חתימה: public void UpdateRate(int numViewers)",
          "פעולה פנימית UpdateRate — public void UpdateRate (int numViewers)"),
        R("q2.א.c1.k2", 3, "לולאה על כל numViewers הצופים",
          "עבור כל צופה הפעולה קולטת …"),
        R("q2.א.c1.k3", 2, "קליטת דירוג מכל צופה בתוך הלולאה",
          "קולטת ומוסיפה את הדירוג שלו"),
        R("q2.א.c1.k4", 3,
          "הוספת כל דירוג שנקלט לדירוג הקיים (rate += …) — צבירה, לא דריסה",
          "מוסיפה את הדירוג שלו לדירוג הקיים … סכום הדירוגים שנקלטו אי פעם"),
    ]),
    # ── q2.ב — LowestRateChannel ────────────────────────────────────────────
    TP("q2.ב.c0", 2, [
        R("q2.ב.c0.k1", 2,
          "כותרת פעולה חיצונית LowestRateChannel המקבלת TvRate ומחזירה מספר ערוץ",
          "פעולה חיצונית LowestRateChannel כותרת הפעולה"),
    ]),
    TP("q2.ב.c1", 2, [
        R("q2.ב.c1.k1", 2,
          "הגדרת מערך צוברים מטיפוס int לערוצים 1-100, בגודל 101",
          "הגדרת מערך צוברים int לכל 100 הערוצים (המערך אמור להיות בגודל 101)"),
    ]),
    TP("q2.ב.c2", 3, [
        R("q2.ב.c2.k1", 3, "לולאת איפוס על מערך הצוברים",
          "לולאה על מערך הצוברים לאיפוס המערך"),
    ]),
    TP("q2.ב.c3.s0", 3, [
        R("q2.ב.c3.s0.k1", 3, "לולאה העוברת על מערך התוכניות TvShows",
          "הגדרת לולאה על מערך התוכניות TvShows מ-0 עד קטן ממש מ-length"),
        T("q2.ב.c3.s0.k2", 0.5, "הלולאה מתחילה מ-0 (לא מ-1)",
          "אם התחילו מ-1 במקום מ-0 להוריד 0.5"),
        T("q2.ב.c3.s0.k3", 1, "הגישה למערך התוכניות נעשית דרך ה-Getter",
          "אם ניגשו למערך TvShows בלי Getter להוריד 1"),
        T("q2.ב.c3.s0.k4", 0.5, "הגבול העליון של הלולאה נכון (קטן ממש מ-length)",
          "אם טעו בגבול העליון של הלולאה להוריד 0.5"),
    ]),
    TP("q2.ב.c3.s1", 2, [
        R("q2.ב.c3.s1.k1", 2, "בתוך הלולאה: בדיקה שהתא אינו null",
          "בדיקה אם התא אינו null"),
    ]),
    TP("q2.ב.c3.s2", 2, [
        R("q2.ב.c3.s2.k1", 2, "קריאת הערוץ של התוכנית הנוכחית",
          "גישה לערוץ GetChl"),
        T("q2.ב.c3.s2.k2", 1, "הקריאה נעשית ע\"י GetChl ולא בגישה ישירה לתכונה chl",
          "אם ניגשו ישירות לתכונה chl להוריד 1"),
    ]),
    TP("q2.ב.c3.s3", 5, [
        R("q2.ב.c3.s3.k1", 5,
          "צבירת הדירוג של התוכנית לתא של הערוץ שלה במערך הצוברים",
          "צבירה של הדירוג של הערוץ (GetChl) לתוך מערך הצוברים במקום של הערוץ הזה"),
        T("q2.ב.c3.s3.k2", 1, "קריאת הדירוג ע\"י GetRate ולא בגישה ישירה לתכונה rate",
          "אם ניגשו ישירות לתכונה rate במקום GetRate להוריד 1"),
    ]),
    TP("q2.ב.c4.s0", 1, [
        R("q2.ב.c4.s0.k1", 1, "הגדרת משתנה מינימום-דירוג + אתחולו",
          "הגדרת מינימום דירוג + אתחול",
          equiv="[A-4/PL-3] מעקב מינימום מרומז דרך arr[minIndex] — ניב "
                "מינימום-אינדקס — שקול למשתנה מפורש"),
    ]),
    # the K2_FORENSICS case-2 terminal: the variable is a channel INDEX
    TP("q2.ב.c4.s1", 1, [
        R("q2.ב.c4.s1.k1", 1,
          "הגדרת משתנה ערוץ-מינימלי + אתחולו — המשתנה מייצג מספר ערוץ (אינדקס), "
          "ומאותחל כערוץ, לא כערך דירוג",
          "הגדרת ערוץ מינימלי +אתחול"),
    ]),
    # [A-2, owner H-4] start-index tariff (yonatan's ratified 1.5) + dan's
    # base-candidate idiom as ratified-full equivalence
    TP("q2.ב.c4.s2", 2, [
        R("q2.ב.c4.s2.k1", 2, "לולאה על מערך הצוברים מ-1 עד 100",
          "הגדרת לולאה על מערך צוברים מ-1 עד 100",
          equiv="[A-2] התחלה מ-2 עם מועמד-בסיס באינדקס 1 שקולה לכיסוי מלא 1..100"),
        T("q2.ב.c4.s2.k2", 0.5,
          "הסריקה מתחילה מ-1, לא מ-0 — תא 0 אינו ערוץ",
          "הגדרת לולאה על מערך צוברים מ-1 עד 100 [A-2 owner tariff]"),
    ]),
    # ⚠ OPEN QUESTION Q-1 (rubric_underdetermined): contract says 3, rubric
    # text says «סה"כ 2 נקודות». Authored: comparison carries all 3; the
    # usage-check is note_only per the rubric's own «לא להוריד, לכתוב הערה».
    TP("q2.ב.c4.s3", 3, [
        R("q2.ב.c4.s3.k1", 3,
          "בתוך הלולאה: השוואת סכום הדירוגים של הערוץ הנוכחי לערך הקיצון הנוכחי "
          "(התנאי שמאתר את הערוץ בעל הדירוג הנמוך)",
          "והאם סה\"כ הדירוגים קטן מהמינימום - סה\"כ 2 נקודות"),
        N("q2.ב.c4.s3.k2",
          "בדיקה שהתא גדול מאפס (כלומר הערוץ בשימוש) — לציין בלבד, ללא ניכוי",
          "בדיקה האם התא … גדול מאפס … - לא להוריד, לכתוב הערה"),
        T("q2.ב.c4.s3.k3", 3,
          "כיוון החיפוש הוא מינימום (ולא מקסימום) — ההשוואה בכיוון קטן-מ",
          "אם חיפשו את המקסימום אך הלוגיקה בסדר להוריד 3"),
    ]),
    TP("q2.ב.c4.s4", 1, [
        R("q2.ב.c4.s4.k1", 1, "בתוך התנאי: עדכון מינימום הדירוג",
          "בתוך התנאי (בתוך הלולאה) - החלפה של מינימום דירוג",
          equiv="[A-4/PL-3] בניב מינימום-אינדקס עדכון האינדקס הוא גם עדכון "
                "המינימום — שקול"),
    ]),
    TP("q2.ב.c4.s5", 1, [
        R("q2.ב.c4.s5.k1", 1, "בתוך התנאי: עדכון הערוץ המינימלי",
          "בתוך התנאי (בתוך הלולאה) - החלפת הערוץ המינימלי"),
    ]),
    TP("q2.ב.c5", 1, [
        R("q2.ב.c5.k1", 1, "החזרת הערוץ המינימלי",
          "החזרת הערוץ המינימלי"),
    ]),
    # ── q2.ג — PrintLowRatingChannel ────────────────────────────────────────
    TP("q2.ג.c0.s0", 2, [
        R("q2.ג.c0.s0.k1", 2,
          "כותרת פעולה חיצונית PrintLowRatingChannel המקבלת TvRate",
          "כותרת הפעולה PrintLowRatingChannel"),
    ]),
    TP("q2.ג.c0.s1", 3, [
        R("q2.ג.c0.s1.k1", 3,
          "מציאת הערוץ המינימלי ע\"י זימון LowestRateChannel (ולא חישוב מחדש)",
          "מציאת הערוץ בעל דירוג מינימלי ע\"י זימון LowestRateChannel"),
    ]),
    TP("q2.ג.c0.s2", 3, [
        R("q2.ג.c0.s2.k1", 3,
          "לולאה על מערך התוכניות TvShows מ-0 עד קטן ממש מ-length",
          "הגדרת לולאה על מערך התוכניות TvShows מ-0 עד קטן ממש מ-length"),
        T("q2.ג.c0.s2.k2", 1, "הגישה למערך נעשית דרך ה-getter",
          "אם הגישה למערך בלי getter להוריד 1"),
    ]),
    # the K2_FORENSICS case-3 terminal: the rubric's own 2+2+2+2 itemization
    TP("q2.ג.c0.s3", 8, [
        R("q2.ג.c0.s3.k1", 2, "בתוך הלולאה: בדיקה שהתוכנית אינה null",
          "אינה null ב (2 נקודות)"),
        R("q2.ג.c0.s3.k2", 2,
          "בדיקה שהערוץ של התוכנית תואם את הערוץ המינימלי ע\"י GetChl",
          "הערוץ שלה תואם את הערוץ המינימלי (ע\"י GetChl והשוואתם (2 נקודות)"),
        R("q2.ג.c0.s3.k3", 2, "בדיקה שהתוכנית באוויר ע\"י GetIsOn",
          "וגם היא באוויר (ע\"י GetIsOn ב 2 נקודות)"),
        R("q2.ג.c0.s3.k4", 2, "הדפסת שם התוכנית ע\"י GetName",
          "הדפסה של השם של התוכנית (ע\"י GetN[ame] ב 2 נקודות)"),
    ]),
]


def main() -> None:
    bundle = load_bundle("dan_basiuk", suite_dir=SUITE)
    plan = GradingPlan(
        plan_version="hobby_tvshow/v2",   # v2 = H-4 ratification + A-1..A-6 (owner, 2026-08-28)
        exam_id="hobby_tvshow (corrected, H1-ratified)",
        rubric_contract_sha256=bundle.rubric_contract_hash,
        terminals=TERMINALS,
    )
    errs = validate_plan(
        plan,
        contract_terminal_points={t: i.points for t, i in bundle.terminal_infos.items()},
        terminal_scopes={t: (i.question_id if i.sub_question_id is None
                             else f"{i.question_id}.{i.sub_question_id}")
                         for t, i in bundle.terminal_infos.items()},
        precision=bundle.rubric_contract.numeric_policy.precision)
    if errs:
        print("PLAN INVALID:")
        for e in errs:
            print("  ", e)
        raise SystemExit(1)

    out = SUITE / "plans" / "hobby_tvshow.plan.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(plan.model_dump_json(indent=1), encoding="utf-8")
    sha = hashlib.sha256(out.read_bytes()).hexdigest()

    n_checks = sum(len(t.checks) for t in plan.terminals)
    kinds = {}
    for t in plan.terminals:
        for c in t.checks:
            kinds[c.kind] = kinds.get(c.kind, 0) + 1
    print(f"PLAN VALID: {len(plan.terminals)} terminals, {n_checks} checks {kinds}")
    print(f"written: {out}")
    print(f"plan_sha256: {sha}")


if __name__ == "__main__":
    main()
