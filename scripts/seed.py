"""
scripts/seed.py
Generates ~60 realistic fictional Indian court judgment JSON files and seeds the database.
"""

import json
import os
import sys
import sqlite3
import random
from pathlib import Path

# Project root is one level up from scripts/
ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
JUDGMENTS_DIR = DATA_DIR / "judgments"
DB_PATH = DATA_DIR / "caselens.db"

# Ensure directories
JUDGMENTS_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────
# DB init (mirrors app/db.py so seed is standalone)
# ─────────────────────────────────────────────

def init_db(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS judgments (
            id          TEXT PRIMARY KEY,
            title       TEXT,
            court       TEXT,
            year        INTEGER,
            case_type   TEXT,
            text_content TEXT
        );
        CREATE TABLE IF NOT EXISTS pending_cases (
            case_no         TEXT PRIMARY KEY,
            title           TEXT,
            description     TEXT,
            case_type       TEXT,
            filing_date     TEXT,
            hearings_so_far INTEGER,
            num_parties     INTEGER,
            is_appeal       INTEGER,
            court           TEXT
        );
    """)
    conn.commit()

# ─────────────────────────────────────────────
# Judgment definitions
# ─────────────────────────────────────────────

JUDGMENTS = []

# ── 1. Section 138 Cheque Bounce (Criminal) ──────────────────────────────────
cheque_cases = [
    {
        "id": "CHQ001",
        "title": "Ramesh Gupta v. Suresh Sharma",
        "court": "Delhi High Court",
        "year": 2019,
        "case_type": "Criminal",
        "text": (
            "The complainant, Suresh Sharma, filed a complaint under Section 138 of the Negotiable "
            "Instruments Act against the drawer, Ramesh Gupta, for dishonour of a cheque of "
            "Rs 5,00,000. The cheque was returned by the bank with the endorsement 'Insufficient "
            "Funds'. The court examined the statutory demand notice sent by the complainant and "
            "found it to be legally valid. The drawer failed to repay the cheque amount within "
            "15 days of receiving the notice. Under Section 138 NI Act, the dishonour of a cheque "
            "drawn for discharge of a legally enforceable debt gives rise to criminal liability. "
            "The court held that the ingredients of the offence are fully established. The "
            "complainant's evidence went unrebutted. The drawer's defence that the cheque was "
            "issued as security was rejected as it was not supported by any contemporaneous "
            "document. The drawer is held guilty under Section 138 of the Negotiable Instruments "
            "Act and sentenced to pay a fine of Rs 10,00,000 with simple imprisonment of one year "
            "in default. The complainant is awarded the cheque amount as compensation under "
            "Section 357 CrPC."
        ),
    },
    {
        "id": "CHQ002",
        "title": "Priya Finance Ltd v. Ajay Kumar",
        "court": "Mumbai Sessions Court",
        "year": 2020,
        "case_type": "Criminal",
        "text": (
            "This is a complaint under Section 138 of the Negotiable Instruments Act. The "
            "complainant, Priya Finance Ltd, advanced a loan of Rs 8,00,000 to the accused, "
            "Ajay Kumar. The accused issued a cheque towards repayment which was dishonoured "
            "on presentation with the remark 'Account Closed'. The complainant duly issued a "
            "statutory legal demand notice within thirty days of dishonour. The drawer failed "
            "to make payment within the stipulated period. The defence raised by the drawer "
            "that the loan was fully repaid was not substantiated by any documentary evidence. "
            "The complainant produced bank statements and the original cheque with bank memo. "
            "The court finds that the dishonour of the cheque is established beyond reasonable "
            "doubt. The drawer is held guilty under Section 138 NI Act. Sentence: two years "
            "simple imprisonment with a fine of Rs 16,00,000 as double the cheque amount "
            "as compensation to the complainant under the Negotiable Instruments Act."
        ),
    },
    {
        "id": "CHQ003",
        "title": "Kavitha Textiles v. Mani Exports",
        "court": "Madras High Court",
        "year": 2021,
        "case_type": "Criminal",
        "text": (
            "The appellant, Kavitha Textiles, challenges the acquittal of the respondent-accused "
            "in a Section 138 NI Act complaint. The cheque of Rs 12,00,000 was dishonoured "
            "with the reason 'Funds Insufficient'. The trial court acquitted the accused on "
            "the ground that the demand notice was served beyond the statutory period. This "
            "High Court examined the speed-post acknowledgement and finds that the notice "
            "was dispatched within 30 days of the dishonour. Under the Negotiable Instruments "
            "Act, the date of dispatch by registered post is the relevant date. The complainant "
            "as drawer of the demand notice duly complied with the procedure. The court sets "
            "aside the acquittal. The drawer is held guilty of the offence under Section 138 "
            "of the Negotiable Instruments Act. The matter is remitted to the trial court for "
            "sentencing after hearing the accused on quantum. The complainant is entitled to "
            "compensation equal to the cheque amount."
        ),
    },
    {
        "id": "CHQ004",
        "title": "Meenakshi Traders v. Rajan & Sons",
        "court": "Delhi High Court",
        "year": 2018,
        "case_type": "Criminal",
        "text": (
            "The complainant instituted this criminal complaint under Section 138 of the "
            "Negotiable Instruments Act alleging dishonour of a cheque of Rs 3,50,000 issued "
            "by the drawer, Rajan & Sons. The cheque was returned unpaid with the endorsement "
            "'Payment Stopped by Drawer'. The stoppage of payment is treated as equivalent to "
            "dishonour under the Negotiable Instruments Act. A demand notice was served "
            "personally on the proprietor. The accused contended that the cheque was obtained "
            "by coercion; however, no FIR was lodged for extortion prior to receiving the "
            "notice, undermining this defence. The complainant proved the transaction through "
            "invoices and delivery receipts. The court holds the accused held guilty under "
            "Section 138 NI Act. Sentence: fine of Rs 7,00,000 payable within two months, "
            "failing which one year simple imprisonment. Appeal against this order shall lie "
            "to the Sessions Court."
        ),
    },
    {
        "id": "CHQ005",
        "title": "State Bank of India v. Deepak Verma",
        "court": "Mumbai Sessions Court",
        "year": 2022,
        "case_type": "Criminal",
        "text": (
            "The complainant bank filed this case under Section 138 of the Negotiable "
            "Instruments Act for dishonour of a cheque of Rs 25,00,000 issued by the accused "
            "in settlement of an overdue term loan. The cheque was dishonoured on two separate "
            "occasions with the remark 'Insufficient Funds'. The complainant issued a statutory "
            "demand notice by registered post as required under the Negotiable Instruments Act. "
            "Despite service of the notice, the drawer neither paid the cheque amount nor gave "
            "any reply. The accused failed to appear despite summons and was tried ex-parte. "
            "Documentary evidence including the dishonoured cheque, bank memo, and registered "
            "post receipt conclusively establish the ingredients of the offence. The drawer is "
            "held guilty under Section 138 NI Act. The court imposes a fine of Rs 50,00,000 "
            "and directs payment of the cheque amount to the complainant as compensation. "
            "In default, the accused shall undergo two years' simple imprisonment."
        ),
    },
    {
        "id": "CHQ006",
        "title": "Leela Enterprises v. Prakash Brothers",
        "court": "Madras High Court",
        "year": 2023,
        "case_type": "Criminal",
        "text": (
            "This revision petition challenges the conviction of the petitioner under Section 138 "
            "of the Negotiable Instruments Act. The cheque of Rs 6,75,000 was dishonoured with "
            "the remark 'Drawer's Signature Differs'. The revisionist argues that signature "
            "mismatch does not constitute dishonour within the meaning of the Negotiable "
            "Instruments Act. This High Court, however, notes that dishonour of a cheque on "
            "any technical ground, including signature mismatch, falls within the ambit of "
            "Section 138 NI Act as interpreted by the Supreme Court in several decisions. "
            "The complainant's evidence that the cheque was issued for a legally enforceable "
            "debt stands unrebutted. The drawer offered no plausible explanation for the "
            "signature discrepancy. The court upholds the conviction of the drawer. The "
            "sentence of fine of Rs 13,50,000 is confirmed. The revision petition is dismissed. "
            "The drawer is held guilty as convicted by the trial court."
        ),
    },
]
JUDGMENTS.extend(cheque_cases)

# ── 2. Tenant Eviction (Property/Civil) ──────────────────────────────────────
eviction_cases = [
    {
        "id": "EVC001",
        "title": "Ramji Lal v. Govind Das",
        "court": "Rajasthan High Court",
        "year": 2019,
        "case_type": "Property/Civil",
        "text": (
            "The landlord, Ramji Lal, filed an eviction petition against the tenant, Govind Das, "
            "under the Rajasthan Rent Control Act on the ground of default in payment of rent "
            "and subletting without consent. The tenancy was established by a registered rent "
            "deed. The tenant claimed to be a protected tenant entitled to protection under the "
            "Rent Control Act. Evidence showed that the tenant had been in arrears of rent for "
            "over 24 months. The landlord duly demanded rent and issued legal notices. "
            "The claim of protected tenant status was negatived as the original tenancy was "
            "created after the threshold date under the Rent Control Act. The court grants the "
            "eviction decree against the tenant. The landlord is entitled to vacant possession. "
            "The tenant is directed to pay arrears of rent of Rs 3,60,000 within 60 days. "
            "Eviction is granted on grounds of default in rent payment under the Rent Control Act."
        ),
    },
    {
        "id": "EVC002",
        "title": "Harbhajan Singh v. Manjit Kaur",
        "court": "Punjab High Court",
        "year": 2020,
        "case_type": "Property/Civil",
        "text": (
            "This first appeal arises from a decree of eviction passed by the Rent Controller "
            "against the tenant, Manjit Kaur. The landlord, Harbhajan Singh, sought eviction "
            "on grounds of personal necessity and non-payment of arrears of rent under the "
            "Punjab Rent Act. The tenant pleaded that she is a protected tenant and that her "
            "tenancy is protected under the Rent Control Act. The appellate court examined the "
            "evidence. The landlord's bona fide need for personal use of the premises was "
            "established through affidavit and medical certificates showing old age. The arrears "
            "of rent for 18 months remained unpaid despite notices. The defence of protected "
            "tenant was not substantiated. The court upholds the eviction decree. The tenant "
            "is granted six months' time to vacate the premises. Arrears of rent shall be "
            "paid before possession is handed over. The landlord succeeds in the eviction petition."
        ),
    },
    {
        "id": "EVC003",
        "title": "Suresh Malhotra v. Dinesh Ahuja",
        "court": "Delhi High Court",
        "year": 2021,
        "case_type": "Property/Civil",
        "text": (
            "The landlord, Suresh Malhotra, initiated eviction proceedings against the tenant, "
            "Dinesh Ahuja, under the Delhi Rent Control Act on grounds of non-payment of rent "
            "and misuse of premises. The tenancy was for commercial purpose but the tenant "
            "converted part of the premises to residential use. Under the Delhi Rent Control Act, "
            "misuse of tenancy premises is a ground for eviction. The tenant argued he was a "
            "protected tenant due to long possession exceeding 10 years. The court examined the "
            "lease deed and rental receipts. The premises were clearly demised for commercial "
            "purposes. The conversion to residential use constitutes breach of the tenancy "
            "agreement and a ground under the Rent Control Act. Eviction is decreed on the "
            "ground of misuse. Additionally, arrears of rent for 15 months remain unpaid "
            "despite repeated demands. The landlord is entitled to immediate possession. "
            "The tenant's claim of protected tenant status is rejected."
        ),
    },
    {
        "id": "EVC004",
        "title": "Vasant Bhatt v. Kantilal Shah",
        "court": "Rajasthan High Court",
        "year": 2018,
        "case_type": "Property/Civil",
        "text": (
            "This revision petition is filed by the tenant, Kantilal Shah, against the eviction "
            "decree under the Rajasthan Rent Control Act. The landlord, Vasant Bhatt, sought "
            "eviction on grounds of personal necessity and arrears of rent. The tenant contended "
            "that the landlord owns alternative accommodation and hence personal necessity is "
            "not established. The revisional court notes that the landlord's children have "
            "returned to the city after completing education and require the premises for "
            "residence. The alternative accommodation owned by the landlord is in a different "
            "locality and bona fide need is not negated by its existence. Arrears of rent of "
            "Rs 1,80,000 were also established. The protected tenant plea raised by the tenant "
            "was not substantiated by documentary evidence. The revision petition is dismissed. "
            "The eviction decree under the Rent Control Act is upheld. The tenant is given "
            "three months to vacate."
        ),
    },
    {
        "id": "EVC005",
        "title": "Gurpreet Kaur v. Ram Lal Sharma",
        "court": "Punjab High Court",
        "year": 2022,
        "case_type": "Property/Civil",
        "text": (
            "The landlady, Gurpreet Kaur, filed an eviction petition under the Punjab Rent "
            "Act against the tenant, Ram Lal Sharma. The ground of eviction is subletting "
            "without prior written consent of the landlady and non-payment of arrears of rent. "
            "The tenancy was created under a registered deed for residential purposes. The "
            "tenant sublet the premises to a third party while continuing to reside elsewhere. "
            "This constitutes a ground for eviction under the Rent Control Act. The tenant "
            "denied subletting and claimed to be a protected tenant. The court inspected the "
            "premises and found third parties in occupation. Arrears of rent for 20 months "
            "were also proved through bank statements and demand notices. The court grants "
            "the eviction decree. The landlady is entitled to possession. The tenant is "
            "directed to clear arrears of rent within 30 days."
        ),
    },
    {
        "id": "EVC006",
        "title": "Ajit Properties v. Shyam Textiles",
        "court": "Delhi High Court",
        "year": 2023,
        "case_type": "Property/Civil",
        "text": (
            "The landlord-company, Ajit Properties, seeks eviction of the tenant, Shyam "
            "Textiles, from commercial premises under the Delhi Rent Control Act. The ground "
            "is non-payment of rent and bonafide requirement for the landlord's own business. "
            "The tenancy has been in existence since 2001. The tenant argues protection under "
            "the Delhi Rent Control Act as a protected tenant. The court examined the standard "
            "rent fixed under the Act and found that the tenant had been paying below the "
            "permissible standard rent for the last 36 months, constituting arrears of rent. "
            "Additionally, the landlord established that it intends to wind down its warehousing "
            "operations and use the suit premises for its retail showroom, which amounts to "
            "bona fide requirement under the Rent Control Act. Eviction is decreed on both "
            "grounds. Possession to be handed over within four months. Arrears of rent to "
            "be settled as directed."
        ),
    },
]
JUDGMENTS.extend(eviction_cases)

# ── 3. Matrimonial / Divorce (Family) ────────────────────────────────────────
matrimonial_cases = [
    {
        "id": "FAM001",
        "title": "Anjali v. Rajesh Kumar",
        "court": "Delhi High Court",
        "year": 2020,
        "case_type": "Family",
        "text": (
            "The petitioner-wife, Anjali, filed a petition for divorce on the ground of cruelty "
            "under Section 13 HMA. The parties were married in 2012 and have been living "
            "separately since 2017. The wife alleged mental cruelty by the husband, including "
            "repeated demands for dowry, verbal abuse, and threats of physical harm. "
            "The husband denied all allegations. The court examined oral and documentary "
            "evidence including WhatsApp messages and medical records. The pattern of conduct "
            "established amounts to mental cruelty within the meaning of Section 13 HMA. "
            "The court finds that the marriage has broken down irretrievably. Continuation of "
            "the marital relationship would cause grave injury to the petitioner. Divorce is "
            "granted under Section 13 HMA on the ground of cruelty. Permanent alimony of "
            "Rs 25,00,000 is awarded to the wife in full and final settlement. Custody of "
            "the minor child is granted to the mother with reasonable visitation rights to "
            "the father."
        ),
    },
    {
        "id": "FAM002",
        "title": "Meera Devi v. Sunil Mehra",
        "court": "Punjab High Court",
        "year": 2021,
        "case_type": "Family",
        "text": (
            "This is a petition for dissolution of marriage under Section 13 HMA on the "
            "ground of irretrievable breakdown of marriage and desertion. The parties "
            "married in 2010 and the respondent-husband deserted the petitioner in 2015 "
            "without reasonable excuse. Despite efforts at reconciliation, including court- "
            "appointed mediation, the parties could not reunite. The court considers the "
            "concept of irretrievable breakdown as recognised by the Supreme Court. The "
            "parties have been living apart for over six years. The marriage has become "
            "a mere legal fiction with no prospect of resumption of cohabitation. The "
            "court grants divorce under Section 13 HMA. The wife is awarded monthly "
            "maintenance of Rs 20,000. The matrimonial home shall be shared between "
            "the parties as per mutual consent arrived at before the court. The court "
            "also notes that mutual consent divorce under Section 13-B HMA would have "
            "been more appropriate given the settled positions."
        ),
    },
    {
        "id": "FAM003",
        "title": "In re: Vikas & Pooja",
        "court": "Rajasthan High Court",
        "year": 2019,
        "case_type": "Family",
        "text": (
            "The parties, Vikas and Pooja, have filed a joint petition for divorce by mutual "
            "consent under Section 13-B of the Hindu Marriage Act (Section 13 HMA). They "
            "married in 2013 and started living separately in 2017. They have worked out all "
            "ancillary matters including alimony of Rs 15,00,000 to be paid by the husband, "
            "custody of their son to the mother, and visitation rights to the father. The "
            "court is satisfied that the consent is free and not obtained by fraud, coercion "
            "or undue influence. Under mutual consent the statutory waiting period of six "
            "months was waived by the court noting that the parties have already been "
            "separated for over eighteen months. The marriage is dissolved by a decree of "
            "divorce by mutual consent under Section 13 HMA. The terms of the settlement "
            "deed are incorporated into the decree. The court records that the irretrievable "
            "breakdown of the marriage is evident from the prolonged separation."
        ),
    },
    {
        "id": "FAM004",
        "title": "Sunita Sharma v. Pankaj Sharma",
        "court": "Madras High Court",
        "year": 2022,
        "case_type": "Family",
        "text": (
            "The wife filed a matrimonial appeal challenging dismissal of her divorce "
            "petition under Section 13 HMA. The ground pleaded was cruelty. The trial "
            "court dismissed the petition holding that occasional quarrels do not amount to "
            "cruelty. This court, on reappraisal of evidence, finds that the husband's "
            "conduct went beyond ordinary domestic discord. He forced the wife to give up "
            "employment, restricted her movements, and subjected her to sustained mental "
            "and emotional abuse. The standard of cruelty under Section 13 HMA does not "
            "require physical violence. The cumulative effect of the husband's conduct "
            "amounts to cruelty making it unreasonable to expect the wife to live with him. "
            "The marriage has irretrievably broken down. The appeal is allowed. Divorce is "
            "granted on the ground of cruelty under Section 13 HMA. Permanent alimony of "
            "Rs 30,00,000 is awarded to the wife. The wife also gets custody of the children."
        ),
    },
    {
        "id": "FAM005",
        "title": "Ramesh Pillai v. Latha Pillai",
        "court": "Kerala High Court",
        "year": 2023,
        "case_type": "Family",
        "text": (
            "The respondent-wife filed a counter-claim for divorce on the ground of cruelty "
            "in matrimonial proceedings initiated by the husband for restitution of conjugal "
            "rights. The court examined evidence of both parties. The husband's claim for "
            "restitution was withdrawn mid-trial. On the wife's counter-claim, the court "
            "examined several incidents of physical assault and verbal abuse documented in "
            "police complaint registers. The husband's conduct amounts to cruelty under "
            "Section 13 HMA. The parties have been in litigation for eight years, reinforcing "
            "the conclusion that the marriage has irretrievably broken down with no possibility "
            "of reconciliation. Under the principle of irretrievable breakdown as applied by "
            "the Supreme Court under Article 142 and followed by High Courts, the marriage is "
            "dissolved. Divorce is granted to the wife under Section 13 HMA. Alimony and "
            "custody matters to be determined in separate proceedings as agreed by the parties."
        ),
    },
]
JUDGMENTS.extend(matrimonial_cases)

# ── 4. Labour / Workman Reinstatement ────────────────────────────────────────
labour_cases = [
    {
        "id": "LAB001",
        "title": "Ramakrishna v. M/s ABC Industries",
        "court": "Delhi High Court",
        "year": 2019,
        "case_type": "Labour",
        "text": (
            "The workman, Ramakrishna, challenges his retrenchment by M/s ABC Industries "
            "as illegal and void under the Industrial Disputes Act. The workman had "
            "continuous service of 8 years when he was retrenched without payment of "
            "retrenchment compensation and without following the last-come-first-go principle "
            "mandated under Section 25G of the Industrial Disputes Act. The employer claimed "
            "the retrenchment was due to surplus labour. The Labour Court found that the "
            "employer did not comply with Section 25F of the Industrial Disputes Act and "
            "ordered reinstatement with back wages. This High Court upholds the Labour "
            "Court award. The retrenchment is declared void ab initio. The workman is "
            "entitled to reinstatement with full back wages and continuity of service under "
            "the Industrial Disputes Act. The employer is directed to reinstate the workman "
            "within 30 days. 50% back wages shall be paid within 60 days."
        ),
    },
    {
        "id": "LAB002",
        "title": "Suresh Kumar v. M/s Bharat Steels",
        "court": "Madras High Court",
        "year": 2020,
        "case_type": "Labour",
        "text": (
            "The workman, Suresh Kumar, was dismissed from service by M/s Bharat Steels "
            "following a domestic enquiry on charges of theft of raw materials. The workman "
            "raised an industrial dispute under the Industrial Disputes Act contending that "
            "the domestic enquiry was conducted in violation of natural justice. The Labour "
            "Court found that the enquiry officer refused to allow the workman to cross-examine "
            "the management's key witness, vitiating the enquiry. Where an enquiry is "
            "defective, the Labour Court is entitled to independently assess the evidence. "
            "On independent assessment, the charges were not proved beyond reasonable doubt. "
            "The Labour Court directed reinstatement with 60% back wages. This writ petition "
            "by the management is dismissed. The Industrial Disputes Act requires fairness in "
            "domestic enquiries. The workman's reinstatement is upheld. The employer shall "
            "comply with the reinstatement order and pay back wages as directed."
        ),
    },
    {
        "id": "LAB003",
        "title": "Meenakshi v. State of Tamil Nadu",
        "court": "Madras High Court",
        "year": 2021,
        "case_type": "Labour",
        "text": (
            "The petitioner-workman, Meenakshi, was engaged as a contract worker for "
            "11 years with the respondent government establishment. She claims regularisation "
            "of service under the Industrial Disputes Act and State government circular on "
            "regularisation of contract workers. The workman performed perennial and "
            "permanent duties identical to regular employees. Under the Industrial Disputes "
            "Act and pursuant to the Supreme Court's decisions on equal pay and regularisation, "
            "continued contract employment for perennial posts is impermissible. The retrenchment "
            "of the workman without following Section 25F of the Industrial Disputes Act is void. "
            "The court directs reinstatement of the workman on a regular post with notional "
            "continuity of service from the date of her initial engagement. Back wages at 50% "
            "are awarded for the period of illegal retrenchment. The workman's service shall "
            "be regularised as directed."
        ),
    },
    {
        "id": "LAB004",
        "title": "Prakash v. M/s National Chemicals",
        "court": "Bombay High Court",
        "year": 2022,
        "case_type": "Labour",
        "text": (
            "The workman, Prakash, was retrenched by M/s National Chemicals citing factory "
            "closure due to losses. The workman raised an industrial dispute under the "
            "Industrial Disputes Act challenging the closure as colourable exercise of power. "
            "Evidence showed that the company did not follow the mandatory procedure under "
            "Chapter VB of the Industrial Disputes Act before closure, as the establishment "
            "employed more than 100 workmen. The Industrial Tribunal found the closure to "
            "be illegal and ordered reinstatement of all retrenched workmen with full back "
            "wages. The company challenged this. The High Court finds that Section 25-O "
            "of the Industrial Disputes Act mandates prior government permission for closure "
            "of large establishments. No such permission was obtained. The retrenchment is "
            "void. The reinstatement order is upheld. The workman is entitled to reinstatement "
            "with continuity of service and full back wages."
        ),
    },
    {
        "id": "LAB005",
        "title": "Ram Sahay v. Rajasthan Government",
        "court": "Rajasthan High Court",
        "year": 2023,
        "case_type": "Labour",
        "text": (
            "The petitioner-workman, Ram Sahay, served as a daily wage worker with the "
            "Public Works Department for 14 years. His services were terminated without "
            "notice or retrenchment compensation under the Industrial Disputes Act. The "
            "workman raised an industrial dispute. The Labour Court found that the workman "
            "had attained the status of a 'workman' under the Industrial Disputes Act by "
            "virtue of continuous engagement exceeding 240 days per year for more than "
            "5 consecutive years. Termination without following Section 25F of the "
            "Industrial Disputes Act is void ab initio. The employer was directed to reinstate "
            "the workman with back wages. This writ petition by the State challenging the "
            "award is dismissed. The Industrial Disputes Act protects workmen against arbitrary "
            "retrenchment. The reinstatement order and 75% back wages are upheld."
        ),
    },
]
JUDGMENTS.extend(labour_cases)

# ── 5. Consumer Forum ─────────────────────────────────────────────────────────
consumer_cases = [
    {
        "id": "CON001",
        "title": "Ramesh Verma v. M/s Star Developers",
        "court": "NCDRC",
        "year": 2020,
        "case_type": "Consumer",
        "text": (
            "The complainant, Ramesh Verma, booked a flat with the opposite party, M/s Star "
            "Developers, in 2015 for Rs 45,00,000 and paid the full booking amount. The "
            "opposite party promised possession by 2018 but failed to deliver the flat. "
            "The complainant filed a complaint before NCDRC alleging deficiency in service "
            "and unfair trade practice. The NCDRC examined the builder-buyer agreement and "
            "found that the opposite party had no reasonable ground for the three-year delay. "
            "Deficiency in service by a builder who fails to deliver possession within the "
            "agreed time is well-established under consumer protection law. The NCDRC "
            "directs the opposite party to either deliver the flat or refund Rs 45,00,000 "
            "with 10% interest from 2018. Additionally, compensation of Rs 5,00,000 for "
            "mental agony and Rs 50,000 for litigation costs is awarded. The complainant "
            "is entitled to full relief as prayed."
        ),
    },
    {
        "id": "CON002",
        "title": "Sunita Kapoor v. Max Insurance Co",
        "court": "NCDRC",
        "year": 2021,
        "case_type": "Consumer",
        "text": (
            "The complainant, Sunita Kapoor, filed this consumer complaint against Max "
            "Insurance Co for wrongful repudiation of her health insurance claim. The "
            "complainant was hospitalised for a cardiac procedure and submitted all "
            "documents for cashless claim settlement. The insurance company repudiated "
            "the claim alleging a pre-existing condition. The NCDRC examined the medical "
            "records and the policy documents. The condition for which hospitalisation "
            "occurred was not covered by the exclusion clause as the complainant had "
            "disclosed all material facts at the time of proposal. Repudiation of a "
            "genuine claim amounts to deficiency in service and unfair trade practice "
            "under the Consumer Protection Act. The complainant is awarded compensation "
            "of Rs 8,50,000 being the claim amount, plus Rs 2,00,000 for mental agony. "
            "The NCDRC directs the insurance company to pay within 30 days with interest."
        ),
    },
    {
        "id": "CON003",
        "title": "Ajay Mehta v. Honda Motors",
        "court": "NCDRC",
        "year": 2019,
        "case_type": "Consumer",
        "text": (
            "The complainant, Ajay Mehta, purchased a new car from the opposite party "
            "which developed serious manufacturing defects within three months of purchase. "
            "Despite six visits to the authorised service centre, the defects could not "
            "be rectified. The complainant sought replacement of the vehicle or refund "
            "before NCDRC. The opposite party denied manufacturing defect and attributed "
            "issues to misuse. The NCDRC appointed an independent technical expert whose "
            "report confirmed inherent manufacturing defects in the engine and gearbox. "
            "Supply of a defective product and failure to rectify it amounts to deficiency "
            "in service. The NCDRC directs the opposite party to replace the vehicle with "
            "a new one of the same model or refund the purchase price of Rs 12,00,000 "
            "with 9% interest. Compensation of Rs 1,00,000 for harassment is also awarded "
            "to the complainant."
        ),
    },
    {
        "id": "CON004",
        "title": "Pradeep Singh v. IndiGo Airlines",
        "court": "NCDRC",
        "year": 2022,
        "case_type": "Consumer",
        "text": (
            "The complainant, Pradeep Singh, missed his connecting international flight "
            "due to a delay caused by the opposite party airline. The airline failed to "
            "provide timely alternate arrangements, leaving the complainant stranded at "
            "the transit airport for 36 hours. The complainant incurred additional hotel "
            "and travel expenses of Rs 1,50,000. A consumer complaint was filed before "
            "NCDRC alleging deficiency in service. The opposite party attributed the "
            "delay to bad weather, which is a force majeure event. The NCDRC examined "
            "the DGCA circulars and found that even during weather delays, the airline "
            "has obligations to provide accommodation and meals to stranded passengers. "
            "Failure to do so constitutes deficiency in service under the Consumer "
            "Protection Act. The complainant is awarded Rs 1,50,000 as reimbursement and "
            "Rs 1,00,000 as compensation for inconvenience and mental agony."
        ),
    },
    {
        "id": "CON005",
        "title": "Kavya Reddy v. ABC Hospital",
        "court": "NCDRC",
        "year": 2023,
        "case_type": "Consumer",
        "text": (
            "The complainant, Kavya Reddy, filed a complaint against ABC Hospital for "
            "medical negligence during surgery performed in 2020. The complainant alleged "
            "that the hospital's negligence during a routine appendectomy led to serious "
            "post-operative complications resulting in a prolonged hospital stay of three "
            "months. The NCDRC appointed a medical expert board which found that the "
            "complications arose from preventable intra-operative error amounting to "
            "medical negligence. Medical negligence by a hospital constitutes deficiency "
            "in service under the Consumer Protection Act. The complainant suffered immense "
            "physical pain and financial loss. The NCDRC awards compensation of Rs 20,00,000 "
            "for pain and suffering, Rs 5,00,000 for additional medical expenses, and "
            "Rs 1,00,000 towards litigation costs. The hospital is directed to pay within "
            "60 days. The complainant is entitled to full compensation as ordered."
        ),
    },
]
JUDGMENTS.extend(consumer_cases)

# ── 6. Income Tax ─────────────────────────────────────────────────────────────
tax_cases = [
    {
        "id": "TAX001",
        "title": "ABC Pvt Ltd v. Commissioner of Income Tax",
        "court": "Delhi High Court",
        "year": 2019,
        "case_type": "Tax",
        "text": (
            "The appellant challenges the assessment order passed by the Commissioner of "
            "Income Tax under Section 143(3) of the Income Tax Act disallowing a deduction "
            "claimed under Section 80C. The Assessing Officer held that the investment "
            "made by the assessee in a specified instrument did not qualify for deduction "
            "under Section 80C as the payment was made after the due date of filing of "
            "return. The Commissioner of Income Tax (Appeals) upheld the disallowance. "
            "The Income Tax Appellate Tribunal reversed the order holding that the "
            "investment was made within the extended time. The department filed this appeal. "
            "The High Court examines Section 80C and the relevant circulars. It holds that "
            "deduction under Section 80C is available if the investment is made before the "
            "due date under Section 139(1). The assessment order disallowing the deduction "
            "is set aside. The appeal of the Commissioner of Income Tax is dismissed."
        ),
    },
    {
        "id": "TAX002",
        "title": "Ramesh Traders v. CIT Chennai",
        "court": "Madras High Court",
        "year": 2020,
        "case_type": "Tax",
        "text": (
            "The assessee, Ramesh Traders, challenges the assessment order under Section "
            "143(3) of the Income Tax Act wherein the Commissioner of Income Tax added "
            "unexplained cash credits to the assessee's income. The assessee argued that "
            "the cash credits represented loans from friends and relatives and filed "
            "confirmations and affidavits. The Commissioner of Income Tax found the "
            "explanation unsatisfactory and made additions. The Income Tax Appellate "
            "Tribunal upheld the assessment order. The High Court examined the evidence. "
            "Mere filing of affidavits without documentary proof of creditworthiness of "
            "creditors is insufficient to discharge the burden of proof. The assessment "
            "order adding cash credits to income under Section 68 is upheld. The deduction "
            "claim under Section 80C for the tax year is allowed in part. The Commissioner "
            "of Income Tax's assessment order is confirmed with modifications."
        ),
    },
    {
        "id": "TAX003",
        "title": "XYZ Ltd v. Deputy Commissioner of Income Tax",
        "court": "Bombay High Court",
        "year": 2021,
        "case_type": "Tax",
        "text": (
            "The petitioner, XYZ Ltd, filed a writ petition challenging a reassessment "
            "notice issued by the Deputy Commissioner of Income Tax under Section 148 of "
            "the Income Tax Act beyond the period of four years. The assessment order for "
            "the relevant year had been passed after regular scrutiny under Section 143(3). "
            "The petitioner argued that reassessment beyond four years requires the "
            "Assessing Officer to show that there was failure to disclose fully and truly "
            "all material facts. The High Court examines the reassessment notice. The "
            "grounds stated by the Commissioner of Income Tax do not indicate any failure "
            "of disclosure. The reassessment notice is merely a change of opinion on the "
            "same facts. The court quashes the reassessment notice. The deduction under "
            "Section 80C allowed in the original assessment order stands. The Commissioner "
            "of Income Tax is restrained from reopening the assessment."
        ),
    },
    {
        "id": "TAX004",
        "title": "Prakash Enterprises v. Income Tax Department",
        "court": "Delhi High Court",
        "year": 2022,
        "case_type": "Tax",
        "text": (
            "This appeal concerns the assessment order passed under Section 143(3) of the "
            "Income Tax Act disallowing export incentive deduction claimed by the assessee. "
            "The Commissioner of Income Tax held that the assessee failed to maintain "
            "separate accounts for export business and domestic business, disentitling it "
            "from claiming deduction under the relevant provision. The Income Tax Appellate "
            "Tribunal held in favour of the assessee. The High Court examined Section 80C "
            "and the relevant deduction provision. The requirement of maintaining separate "
            "accounts is directory and not mandatory. The Commissioner of Income Tax "
            "cannot deny a legitimately earned deduction on a technical ground. The "
            "assessment order is set aside in relation to the disallowance. The deduction "
            "is allowed. The Commissioner of Income Tax's appeal is dismissed."
        ),
    },
    {
        "id": "TAX005",
        "title": "Meena Textiles v. CIT Rajasthan",
        "court": "Rajasthan High Court",
        "year": 2023,
        "case_type": "Tax",
        "text": (
            "The assessee, Meena Textiles, challenges the penalty imposed by the "
            "Commissioner of Income Tax under Section 271(1)(c) of the Income Tax Act "
            "for alleged concealment of income in the assessment year under Section 143(3). "
            "The Assessing Officer made additions to income by disallowing certain expenses. "
            "The Commissioner of Income Tax imposed penalty on the ground that the "
            "disallowance of expenses indicates concealment. The Income Tax Appellate "
            "Tribunal deleted the penalty. The High Court affirms. Mere disallowance of "
            "expenses does not by itself amount to concealment of income warranting "
            "penalty under Section 271(1)(c). The deduction was claimed on a debatable "
            "and bona fide interpretation of the provision. The assessment order and "
            "the penalty order stand modified. The Commissioner of Income Tax's appeal "
            "against deletion of penalty is dismissed."
        ),
    },
]
JUDGMENTS.extend(tax_cases)

# ── 7. Constitutional / Writ ──────────────────────────────────────────────────
constitutional_cases = [
    {
        "id": "WRT001",
        "title": "Ram Prasad v. State of Uttar Pradesh",
        "court": "Allahabad High Court",
        "year": 2019,
        "case_type": "Constitutional/Writ",
        "text": (
            "The petitioner, Ram Prasad, filed this writ petition under Article 226 of the "
            "Constitution of India seeking a writ of mandamus directing the State government "
            "to reinstate him in service and pay arrears of salary. The petitioner was "
            "dismissed from service without following the procedure prescribed under Article "
            "311. The High Court exercising its extraordinary jurisdiction under Article 226 "
            "examines whether the fundamental rights of the petitioner under Article 21 have "
            "been violated. The dismissal order was passed without conducting a disciplinary "
            "inquiry, violating the principles of natural justice and the petitioner's "
            "fundamental rights. The court issues a writ of mandamus directing reinstatement. "
            "The State is directed to pay 50% back wages. The order of dismissal is quashed "
            "as it violates the guarantee of livelihood which is part of the fundamental "
            "right to life under Article 21 of the Constitution."
        ),
    },
    {
        "id": "WRT002",
        "title": "Student Federation v. University of Delhi",
        "court": "Delhi High Court",
        "year": 2020,
        "case_type": "Constitutional/Writ",
        "text": (
            "The petitioner, a student federation, filed a writ petition under Article 226 "
            "challenging the university's decision to increase examination fees by 300% "
            "without following any transparent procedure. The petition alleged violation "
            "of the fundamental right to education as a component of the right to life "
            "under Article 21 of the Constitution of India. The High Court issued a "
            "writ of mandamus to the university to disclose the basis for the fee hike "
            "and to hold consultations with student representatives. The arbitrary "
            "increase in fees without due process violates the principles of natural "
            "justice and the fundamental rights of students. The High Court directs the "
            "university to constitute a Fee Revision Committee and to maintain fee "
            "levels until the committee reports. This order exercises the High Court's "
            "power under Article 226 to enforce fundamental rights against institutions "
            "performing public functions."
        ),
    },
    {
        "id": "WRT003",
        "title": "Mukesh Sharma v. State of Haryana",
        "court": "Punjab and Haryana High Court",
        "year": 2021,
        "case_type": "Constitutional/Writ",
        "text": (
            "The petitioner, Mukesh Sharma, challenges his detention under the National "
            "Security Act through a writ petition under Article 226 of the Constitution. "
            "The detention order was not served promptly, and the grounds of detention "
            "were vague and did not enable the petitioner to make an effective representation. "
            "The right to make a representation is a fundamental right under Article 22(5) "
            "of the Constitution. The High Court under Article 226 examines the detention "
            "order meticulously. The grounds of detention are found to be stale and do not "
            "satisfy the requirements of the National Security Act. The detention order "
            "is quashed by a writ of mandamus. The fundamental rights of the petitioner "
            "under Articles 21 and 22 have been violated. The respondent-State is directed "
            "to release the petitioner forthwith. The court reaffirms that preventive "
            "detention statutes must be strictly construed to protect fundamental rights."
        ),
    },
    {
        "id": "WRT004",
        "title": "Priya NGO v. Municipal Corporation",
        "court": "Bombay High Court",
        "year": 2022,
        "case_type": "Constitutional/Writ",
        "text": (
            "The petitioner NGO filed a public interest writ petition under Article 226 "
            "of the Constitution alleging that the Municipal Corporation was failing to "
            "provide safe drinking water to slum dwellers, violating their fundamental "
            "right to life under Article 21. The petition sought a writ of mandamus "
            "directing the Corporation to lay pipelines in identified slum areas within "
            "six months. The High Court, exercising its jurisdiction under Article 226 "
            "in a public interest matter, examines the Municipal Corporation's duty under "
            "the Constitution and municipal law. The right to clean drinking water is "
            "an aspect of the fundamental right to life. The High Court issues a writ "
            "of mandamus directing the Corporation to submit a time-bound action plan "
            "within four weeks and to complete water supply infrastructure within one year. "
            "The fundamental rights of the slum dwellers cannot be allowed to be violated "
            "for want of administrative will."
        ),
    },
    {
        "id": "WRT005",
        "title": "Traders Association v. State of Maharashtra",
        "court": "Bombay High Court",
        "year": 2023,
        "case_type": "Constitutional/Writ",
        "text": (
            "The petitioner, a traders' association, filed a writ petition under Article 226 "
            "of the Constitution challenging a State government order imposing sudden shop "
            "closure timings without any notice or opportunity of hearing. The petition "
            "alleges violation of the fundamental right to carry on trade and profession "
            "under Article 19(1)(g) of the Constitution of India. The High Court under "
            "Article 226 issues a writ of mandamus staying the government order. The order "
            "was passed without following mandatory procedural requirements. The State may "
            "regulate business hours under its police powers, but must follow due process "
            "and afford stakeholders an opportunity to be heard. The fundamental right of "
            "traders to carry on business cannot be curtailed by an arbitrary executive fiat. "
            "The State is directed to issue fresh notice and conduct consultations before "
            "issuing any revised shop closure order."
        ),
    },
]
JUDGMENTS.extend(constitutional_cases)

# ── 8. Contract Breach ────────────────────────────────────────────────────────
contract_cases = [
    {
        "id": "CNT001",
        "title": "Infra Solutions v. Highway Corp",
        "court": "Delhi High Court",
        "year": 2019,
        "case_type": "Contract",
        "text": (
            "The plaintiff, Infra Solutions, filed a civil suit for damages against the "
            "defendant, Highway Corp, for breach of contract. The parties entered into a "
            "contract for construction of a highway stretch for a consideration of Rs 15 crore. "
            "The defendant terminated the contract mid-way without reasonable cause, causing "
            "loss of profits and sunk costs to the plaintiff. A breach of contract occurs "
            "when a party repudiates its obligations without lawful justification. The "
            "plaintiff proved expenditure and loss of expected profits through audited accounts. "
            "The defendant's plea that the termination was for performance failure was not "
            "established. The court grants damages of Rs 4,50,00,000 for breach of contract, "
            "computed as loss of profit on balance work plus sunk costs. Specific performance "
            "is not granted as the contract is for personal services. Interest at 9% per annum "
            "is awarded from date of breach till realisation. Consideration paid is to be "
            "refunded as a component of damages."
        ),
    },
    {
        "id": "CNT002",
        "title": "Rahul Builders v. Sunrise Hotels",
        "court": "Bombay High Court",
        "year": 2020,
        "case_type": "Contract",
        "text": (
            "The plaintiff, Rahul Builders, seeks specific performance of an agreement for "
            "sale of immovable property entered into with the defendant, Sunrise Hotels, for "
            "a consideration of Rs 8 crore. The defendant refused to execute the sale deed "
            "on the agreed date claiming the consideration was inadequate at current market "
            "rates. The defendant's refusal constitutes breach of contract. The plaintiff "
            "duly tendered the full consideration amount on the stipulated date. Under Section "
            "10 of the Specific Relief Act, specific performance of a contract to transfer "
            "immovable property may be ordered where damages are not an adequate remedy. "
            "Real property has unique value and damages would not adequately compensate "
            "the plaintiff. The court grants a decree of specific performance directing the "
            "defendant to execute the sale deed within 60 days. The plaintiff shall deposit "
            "the balance consideration amount in court. Breach of contract in this case "
            "entitles the plaintiff to specific performance as the primary relief."
        ),
    },
    {
        "id": "CNT003",
        "title": "Meera Exports v. Global Commodities",
        "court": "Madras High Court",
        "year": 2021,
        "case_type": "Contract",
        "text": (
            "The plaintiff, Meera Exports, claims damages for breach of contract against the "
            "defendant, Global Commodities, for failure to supply contracted goods on the "
            "agreed date. The defendant failed to deliver 500 metric tonnes of raw cotton "
            "as per the supply agreement. This caused the plaintiff to source the goods at "
            "higher market rates, resulting in losses. Under the law of contract, the measure "
            "of damages for breach of contract in a supply agreement is the difference between "
            "the contract price and the market price on the date of breach. The defendant's "
            "plea of force majeure due to floods was rejected as the defendant did not issue "
            "a force majeure notice as required by the contract and failed to prove the event. "
            "Breach of contract is established. The court awards damages of Rs 1,20,00,000 "
            "as the difference between market price and contract price. Additional damages "
            "for consequential losses are denied as they were not foreseeable. Consideration "
            "in the matter of costs is in favour of the plaintiff."
        ),
    },
    {
        "id": "CNT004",
        "title": "Tech Labs v. SoftServe Inc",
        "court": "Delhi High Court",
        "year": 2022,
        "case_type": "Contract",
        "text": (
            "The plaintiff, Tech Labs, filed a suit for breach of contract and damages against "
            "the defendant, SoftServe Inc, for failure to deliver customised software by the "
            "agreed date. The parties had entered into a software development agreement for "
            "a consideration of Rs 2,50,00,000. The defendant delivered a product that was "
            "deficient and did not meet the agreed specifications. The breach of contract "
            "was established through expert testimony comparing the delivered product against "
            "the technical specifications appended to the agreement. The court examined whether "
            "specific performance should be ordered. Since the software can be developed by "
            "another vendor, damages are an adequate remedy and specific performance is not "
            "granted. The defendant is directed to refund the advance consideration of "
            "Rs 1,25,00,000 and pay damages of Rs 75,00,000 for the additional cost of "
            "re-development. Breach of contract is thus compensated."
        ),
    },
    {
        "id": "CNT005",
        "title": "Suresh Garments v. Fashion House",
        "court": "Rajasthan High Court",
        "year": 2023,
        "case_type": "Contract",
        "text": (
            "The plaintiff, Suresh Garments, claims specific performance and damages for "
            "breach of contract against the defendant, Fashion House. The parties executed "
            "a franchise agreement for a consideration of Rs 50,00,000. After the plaintiff "
            "paid the full consideration and invested in the franchise setup, the defendant "
            "unilaterally terminated the agreement without cause. The plaintiff sought "
            "specific performance or in the alternative damages. The court holds that "
            "specific performance of a franchise agreement is not feasible as it requires "
            "co-operation and trust between the parties, which is absent after acrimonious "
            "termination. However, the breach of contract entitles the plaintiff to substantial "
            "damages. The damages include the consideration paid, infrastructure investment "
            "made in reliance on the contract, and loss of anticipated profits for the "
            "agreed term. Total damages of Rs 2,20,00,000 are awarded for breach of "
            "contract. Interest at 10% per annum is added."
        ),
    },
]
JUDGMENTS.extend(contract_cases)

# ── 9. Additional Varied Cases (~18 more) ────────────────────────────────────
additional_cases = [
    # Motor accident
    {
        "id": "MAC001",
        "title": "Deepa v. State of Karnataka (Motor Accident)",
        "court": "Karnataka High Court",
        "year": 2020,
        "case_type": "Criminal",
        "text": (
            "The claimant, Deepa, filed a motor accident claim petition seeking compensation "
            "for injuries sustained in a road accident caused by a rash and negligent driver. "
            "The Motor Accident Claims Tribunal awarded Rs 8,00,000. This appeal challenges "
            "the quantum. Medical evidence shows permanent disability of 35%. The court "
            "applies the structured formula for compensation under the Motor Vehicles Act "
            "including loss of income, medical expenses, and pain and suffering. Enhanced "
            "compensation of Rs 15,00,000 is awarded. The insurance company is directed to "
            "pay the enhanced amount. The claimant is entitled to full compensation."
        ),
    },
    {
        "id": "MAC002",
        "title": "Ramesh Patel v. Jeevan Insurance",
        "court": "Gujarat High Court",
        "year": 2021,
        "case_type": "Criminal",
        "text": (
            "A motor accident fatality claim. The deceased was 32 years old with a monthly "
            "income of Rs 40,000. The MACT awarded Rs 25,00,000. The claimants, being the "
            "widow and two minor children, seek enhanced compensation. Under the Pranay "
            "Sethi guidelines and the Motor Vehicles Act, the multiplier applicable is 16. "
            "The court recalculates: notional income addition, 50% addition for future "
            "prospects, multiplier application, plus conventional heads including loss of "
            "consortium and loss of estate. Enhanced compensation of Rs 65,00,000 is "
            "awarded. The insurance company shall pay interest at 9% from date of petition. "
            "The claimants are entitled to the enhanced amount."
        ),
    },
    # Property dispute
    {
        "id": "PRD001",
        "title": "Suresh v. Ramesh (Property Partition)",
        "court": "Punjab High Court",
        "year": 2019,
        "case_type": "Property/Civil",
        "text": (
            "A suit for partition of ancestral property. The plaintiff claims one-half share "
            "in the suit property being a co-sharer. The defendant denies the plaintiff's share "
            "alleging an oral partition. The court finds that oral partition of immovable "
            "property is not legally valid under the Transfer of Property Act. The plaintiff's "
            "share is established through the revenue records. A preliminary decree for "
            "partition and separate possession is passed. The parties are directed to "
            "appoint a court commissioner to suggest a physical division of the property. "
            "If the property cannot be equitably divided, it shall be sold by auction "
            "and proceeds divided equally. The plaintiff is entitled to half the property "
            "as co-sharer."
        ),
    },
    {
        "id": "PRD002",
        "title": "Kavita Devi v. Land Acquisition Officer",
        "court": "Rajasthan High Court",
        "year": 2022,
        "case_type": "Constitutional/Writ",
        "text": (
            "The petitioner, Kavita Devi, challenged the land acquisition proceedings under "
            "Article 226 of the Constitution alleging that the Land Acquisition Officer "
            "awarded inadequate compensation for her agricultural land acquired for a highway "
            "project. The court, exercising jurisdiction under Article 226, finds that "
            "the Land Acquisition Officer did not properly apply the market value formula. "
            "A writ of mandamus is issued directing reconsideration of the compensation. "
            "The fundamental right to property as a legal right under Article 300A requires "
            "payment of fair compensation. The court also notes that the acquisition did not "
            "comply with rehabilitation provisions under the Right to Fair Compensation Act. "
            "The petitioner is entitled to enhanced compensation and benefits under the "
            "rehabilitation package. The High Court directs fresh compensation assessment."
        ),
    },
    # Criminal – murder/IPC
    {
        "id": "CRL001",
        "title": "State v. Mohit Kumar",
        "court": "Delhi High Court",
        "year": 2020,
        "case_type": "Criminal",
        "text": (
            "The State of Delhi challenges the acquittal of the accused, Mohit Kumar, in "
            "a murder trial. The Sessions Court acquitted the accused primarily on the "
            "ground that the eyewitnesses were related to the deceased and hence unreliable. "
            "The High Court notes that relationship is not a ground per se to discard "
            "testimony of witnesses. The injured eyewitness gave a cogent and consistent "
            "account. The circumstantial evidence including the discovery of the weapon "
            "at the accused's instance also corroborates the prosecution case. The High "
            "Court reverses the acquittal and convicts the accused under Section 302 IPC. "
            "Considering the nature of the crime and lack of provocation, the sentence "
            "is life imprisonment with fine. The complainant's family is entitled to "
            "victim compensation under the scheme."
        ),
    },
    {
        "id": "CRL002",
        "title": "State v. Ravi Shankar (NDPS)",
        "court": "Punjab and Haryana High Court",
        "year": 2021,
        "case_type": "Criminal",
        "text": (
            "The accused, Ravi Shankar, was convicted by the Sessions Court under the "
            "NDPS Act for possession of commercial quantity of narcotic drugs. This "
            "appeal challenges the conviction on grounds of non-compliance with Section "
            "50 of the NDPS Act, which requires search of a person to be conducted in "
            "the presence of a Gazetted Officer or a Magistrate if the accused so desires. "
            "The High Court examines the evidence of the police witnesses. The mandatory "
            "requirements of Section 50 were duly complied with as the accused was given "
            "the option and waived it in writing. The recovery is established beyond doubt. "
            "The conviction under the NDPS Act is upheld. However, considering the accused's "
            "cooperation during investigation, the sentence is reduced to the minimum "
            "prescribed under the NDPS Act with fine. The complainant is the State."
        ),
    },
    {
        "id": "CRL003",
        "title": "Pooja v. State (Domestic Violence)",
        "court": "Madras High Court",
        "year": 2022,
        "case_type": "Criminal",
        "text": (
            "The petitioner-wife, Pooja, filed this revision challenging dismissal of her "
            "application under the Protection of Women from Domestic Violence Act. The "
            "Magistrate dismissed her application for protection orders and residence orders. "
            "The High Court examines the affidavit of the complainant and other evidence. "
            "The complainant suffered domestic violence within the shared household. The "
            "Domestic Violence Act is benevolent legislation for protection of women. "
            "The High Court sets aside the Magistrate's order and grants a protection order "
            "restraining the respondent-husband from committing acts of domestic violence. "
            "A residence order permitting the complainant to reside in the shared household "
            "is also issued. Monetary relief of Rs 15,000 per month for maintenance is "
            "awarded under the Domestic Violence Act. The complainant is entitled to all "
            "reliefs as prayed."
        ),
    },
    # Cheque bounce variant (additional)
    {
        "id": "CHQ007",
        "title": "National Traders v. Kapil Dutta",
        "court": "Delhi High Court",
        "year": 2022,
        "case_type": "Criminal",
        "text": (
            "The complainant, National Traders, filed a complaint under Section 138 of the "
            "Negotiable Instruments Act for dishonour of a cheque of Rs 9,80,000. The "
            "cheque was dishonoured with the remark 'Exceeds Arrangement'. The drawer, "
            "Kapil Dutta, raised a defence that the cheque was given as security and not "
            "for discharge of a debt. The court examined the written agreement between "
            "the parties which clearly records the debt. Under Section 139 of the Negotiable "
            "Instruments Act, there is a presumption in favour of the holder that the cheque "
            "was issued for a legally enforceable debt. The drawer failed to rebut this "
            "presumption. The dishonour of the cheque is established. The drawer is held "
            "guilty under Section 138 NI Act. Sentence: fine of Rs 20,00,000. The "
            "complainant is awarded the cheque amount with interest."
        ),
    },
    # Eviction variant (additional)
    {
        "id": "EVC007",
        "title": "Mohan Lal v. Abdul Rehman",
        "court": "Delhi High Court",
        "year": 2019,
        "case_type": "Property/Civil",
        "text": (
            "The landlord, Mohan Lal, seeks eviction of the tenant, Abdul Rehman, from "
            "a commercial property under the Delhi Rent Control Act. The ground of eviction "
            "is bona fide requirement of the landlord for his son's business. The tenant "
            "disputes the bona fide nature of the requirement and claims to be a protected "
            "tenant. The court examines the affidavit of the landlord and his son. The "
            "son has acquired professional qualifications and needs premises to start his "
            "business. The landlord has no other suitable vacant commercial premises. "
            "The bona fide requirement is established. The claim of protected tenant status "
            "under the Rent Control Act is negatived as the tenancy was created after the "
            "relevant date. Eviction is decreed. The tenant is given four months to vacate. "
            "Arrears of rent shall be settled at the prevailing standard rent under the Act."
        ),
    },
    # Insurance
    {
        "id": "INS001",
        "title": "Prakash v. New India Assurance",
        "court": "NCDRC",
        "year": 2020,
        "case_type": "Consumer",
        "text": (
            "The complainant, Prakash, filed a consumer complaint against the insurance "
            "company for repudiation of his fire insurance claim. The complainant's factory "
            "suffered fire damage and he submitted a claim for Rs 35,00,000. The insurance "
            "company repudiated the claim alleging deliberate arson. The NCDRC examined "
            "the fire brigade report and police investigation. No case of arson was proved. "
            "The repudiation of a genuine claim amounts to deficiency in service under the "
            "Consumer Protection Act. The complainant is entitled to the insured amount. "
            "The NCDRC directs the insurance company to pay Rs 35,00,000 as claim amount "
            "with 12% interest from the date of repudiation. Additional compensation of "
            "Rs 2,00,000 for mental agony is awarded. The complainant's case is fully proved."
        ),
    },
    # Bankruptcy
    {
        "id": "IBC001",
        "title": "ABC Bank v. XYZ Steels (IBC)",
        "court": "NCLT Delhi",
        "year": 2021,
        "case_type": "Contract",
        "text": (
            "The financial creditor, ABC Bank, filed this application before NCLT under "
            "Section 7 of the Insolvency and Bankruptcy Code (IBC) for initiation of "
            "Corporate Insolvency Resolution Process (CIRP) against the corporate debtor, "
            "XYZ Steels. The financial debt of Rs 120 crore is established through loan "
            "agreements and default is established from bank statements. The corporate "
            "debtor failed to repay the debt. The threshold under IBC for initiating CIRP "
            "is crossed. Under IBC, upon satisfaction of a financial debt and default, the "
            "adjudicating authority has no discretion to refuse admission. CIRP is admitted. "
            "An Interim Resolution Professional is appointed. The moratorium under Section "
            "14 of IBC comes into force. The financial creditor is entitled to participate "
            "in the Committee of Creditors. The corporate debtor's management stands "
            "suspended during CIRP."
        ),
    },
    {
        "id": "IBC002",
        "title": "Operational Creditor v. Real Estate Co",
        "court": "NCLT Mumbai",
        "year": 2022,
        "case_type": "Contract",
        "text": (
            "The operational creditor filed an application under Section 9 of the IBC for "
            "initiating CIRP against the corporate debtor for non-payment of operational "
            "debt of Rs 2,50,00,000 for supply of goods. A demand notice under Section 8 "
            "of IBC was served but the corporate debtor neither paid the debt nor disputed "
            "the existence of the operational debt. Under IBC, upon satisfaction of the "
            "threshold conditions, CIRP is to be admitted. The corporate debtor raised a "
            "plea of pre-existing dispute in the invoice. The NCLT finds that the alleged "
            "dispute was not raised before issuance of the Section 8 notice and hence is "
            "a post-notice dispute not qualifying as a pre-existing dispute under IBC. "
            "CIRP is admitted. An Interim Resolution Professional is appointed. The "
            "moratorium under Section 14 of IBC applies with immediate effect."
        ),
    },
    # Arbitration
    {
        "id": "ARB001",
        "title": "Infrastructure Ltd v. NHAI",
        "court": "Delhi High Court",
        "year": 2020,
        "case_type": "Contract",
        "text": (
            "The petitioner, Infrastructure Ltd, files an application under Section 11 of "
            "the Arbitration and Conciliation Act for appointment of an arbitrator in a "
            "dispute with NHAI arising from a highway construction contract. The contract "
            "contains an arbitration clause. NHAI resisted the application claiming the "
            "dispute does not fall within the arbitration clause. The High Court examines "
            "the arbitration clause and the nature of the dispute. Under Section 11 of the "
            "Arbitration Act, the court's enquiry is limited to the existence of a valid "
            "arbitration agreement. The arbitration clause is wide and covers all disputes "
            "arising from the contract. The alleged breach of contract and consequential "
            "damages claimed by the petitioner fall squarely within the arbitration clause. "
            "The court appoints a retired High Court judge as sole arbitrator. The parties "
            "are directed to appear before the arbitrator within 15 days. The consideration "
            "for specific performance is to be adjudicated by the arbitrator."
        ),
    },
    # Cheque (additional)
    {
        "id": "CHQ008",
        "title": "Siddharth Traders v. Reena Shah",
        "court": "Mumbai Sessions Court",
        "year": 2023,
        "case_type": "Criminal",
        "text": (
            "The complainant, Siddharth Traders, filed a complaint under Section 138 of "
            "the Negotiable Instruments Act against the accused, Reena Shah, for dishonour "
            "of a cheque of Rs 4,25,000. The cheque was dishonoured due to 'Insufficient "
            "Funds'. A demand notice was sent by registered post. The accused filed a "
            "written reply to the demand notice denying liability but failed to pay. "
            "Before the court, the accused admitted her signature on the cheque but claimed "
            "it was a blank signed cheque given as security. The complainant produced "
            "account books and invoices establishing the debt. The defence of blank cheque "
            "given as security was not corroborated by any independent evidence. The "
            "presumption under Section 139 NI Act operates in favour of the complainant. "
            "The drawer, Reena Shah, is held guilty under Section 138 of the Negotiable "
            "Instruments Act. Fine of Rs 8,50,000 imposed with one year imprisonment in default."
        ),
    },
    # Adoption
    {
        "id": "FAM006",
        "title": "In re: Adoption of minor child by Gita Devi",
        "court": "Madras High Court",
        "year": 2021,
        "case_type": "Family",
        "text": (
            "The petitioner, Gita Devi, seeks a declaration of valid adoption of a minor "
            "child under the Hindu Adoptions and Maintenance Act. The child was adopted "
            "from an orphanage with valid consent of the orphanage authority. The adoption "
            "deed was registered. The Court examines whether all conditions for a valid "
            "adoption under the Hindu Adoptions and Maintenance Act are satisfied. The "
            "petitioner is a widow and is otherwise eligible to adopt under the Act. "
            "The child was lawfully given in adoption. The adoption ceremony was performed "
            "as required under the Act. The court is satisfied that the adoption is valid "
            "and legal. A declaration is granted that the minor child stands adopted by "
            "Gita Devi and is entitled to all rights of a natural born child including "
            "inheritance rights under Hindu law. The petitioner's rights as adoptive "
            "mother are fully recognised by this court."
        ),
    },
    # Service law
    {
        "id": "SRV001",
        "title": "Dr. Ramesh v. AIIMS",
        "court": "Delhi High Court",
        "year": 2022,
        "case_type": "Constitutional/Writ",
        "text": (
            "The petitioner, Dr. Ramesh, filed a writ petition under Article 226 of the "
            "Constitution challenging his compulsory retirement from AIIMS. The petitioner "
            "alleged that the retirement was motivated by malice and that the Annual "
            "Confidential Reports (ACRs) on which it was based were tampered with. "
            "The court issues a writ of mandamus to AIIMS to produce original ACRs. "
            "Examination of the ACRs reveals unexplained alterations. Natural justice requires "
            "that an employee be given an opportunity to respond to adverse ACR entries. "
            "The fundamental right to continue in public employment cannot be curtailed "
            "by a tainted process. The court quashes the compulsory retirement order. "
            "Dr. Ramesh is to be reinstated with all consequential benefits. The court "
            "also directs that his ACRs be expunged of the adverse entries, which were "
            "made in violation of the established procedure."
        ),
    },
    # Environmental
    {
        "id": "ENV001",
        "title": "Green Society v. State of Punjab (Pollution)",
        "court": "Punjab and Haryana High Court",
        "year": 2023,
        "case_type": "Constitutional/Writ",
        "text": (
            "A public interest writ petition under Article 226 challenges continued "
            "operation of an industrial unit discharging untreated effluents into a "
            "river. The petitioner, an NGO, seeks closure of the polluting unit. "
            "The court examines reports of the State Pollution Control Board which "
            "confirm persistent violations of effluent discharge standards. The right "
            "to a clean environment is a facet of the fundamental right to life under "
            "Article 21 of the Constitution. The High Court issues a writ of mandamus "
            "directing the Pollution Control Board to seal the polluting unit within "
            "72 hours. The industrial unit shall not be allowed to resume operations "
            "until it installs certified effluent treatment plants. The court also "
            "imposes a fine of Rs 50,00,000 to be deposited with the Pollution "
            "Control Board for river restoration. The fundamental rights of citizens "
            "to a clean environment must be enforced."
        ),
    },
    # Cheque (additional)
    {
        "id": "CHQ009",
        "title": "MNO Finance v. Ajay Sharma",
        "court": "Madras High Court",
        "year": 2019,
        "case_type": "Criminal",
        "text": (
            "The complainant, MNO Finance, filed this petition under Section 138 of the "
            "Negotiable Instruments Act against the drawer, Ajay Sharma, for dishonour of "
            "three cheques totalling Rs 15,00,000. All three cheques were dishonoured with "
            "the remark 'Insufficient Funds'. Demand notices were sent in respect of each "
            "cheque. The drawer failed to pay within the statutory period. The complaints "
            "were tried together. The drawer raised a plea that the cheques were post-dated "
            "and given as security deposits. However, the complainant's ledger showed "
            "corresponding loan disbursals for each cheque. Under Section 138 NI Act and "
            "the Negotiable Instruments Act, the drawer is held guilty in respect of all "
            "three cheques. Consolidated fine of Rs 30,00,000 is imposed. In default, "
            "two years simple imprisonment. The complainant is entitled to the cheque "
            "amounts as compensation."
        ),
    },
]
JUDGMENTS.extend(additional_cases)

# ─────────────────────────────────────────────
# Pending cases
# ─────────────────────────────────────────────

PENDING_CASES = [
    {
        "case_no": "CRL/2024/001",
        "title": "State v. Ravi Kumar (Assault)",
        "description": "Criminal case involving alleged assault under IPC Section 325.",
        "case_type": "Criminal",
        "filing_date": "2024-01-15",
        "hearings_so_far": 5,
        "num_parties": 2,
        "is_appeal": 0,
        "court": "Delhi Sessions Court",
    },
    {
        "case_no": "CIV/2024/002",
        "title": "Ajay Builders v. Kumar Constructions",
        "description": "Civil suit for breach of construction contract and recovery of advance payment.",
        "case_type": "Contract",
        "filing_date": "2023-11-20",
        "hearings_so_far": 8,
        "num_parties": 3,
        "is_appeal": 0,
        "court": "Delhi High Court",
    },
    {
        "case_no": "FAM/2023/003",
        "title": "Anjali v. Suresh (Divorce)",
        "description": "Matrimonial petition for divorce on ground of cruelty under Section 13 HMA.",
        "case_type": "Family",
        "filing_date": "2023-06-10",
        "hearings_so_far": 12,
        "num_parties": 2,
        "is_appeal": 0,
        "court": "Family Court Delhi",
    },
    {
        "case_no": "LAB/2024/004",
        "title": "Mohan v. M/s Steel Corp (Retrenchment)",
        "description": "Industrial dispute challenging retrenchment under Industrial Disputes Act.",
        "case_type": "Labour",
        "filing_date": "2024-03-05",
        "hearings_so_far": 3,
        "num_parties": 2,
        "is_appeal": 0,
        "court": "Labour Court Mumbai",
    },
    {
        "case_no": "TAX/2023/005",
        "title": "ABC Pvt Ltd v. CIT (Tax Assessment)",
        "description": "Appeal against assessment order disallowing business deductions.",
        "case_type": "Tax",
        "filing_date": "2023-08-25",
        "hearings_so_far": 7,
        "num_parties": 2,
        "is_appeal": 1,
        "court": "ITAT Delhi",
    },
    {
        "case_no": "WRT/2024/006",
        "title": "Citizens Forum v. MCD (Writ)",
        "description": "Writ petition under Article 226 for mandamus directing MCD to provide drainage.",
        "case_type": "Constitutional/Writ",
        "filing_date": "2024-01-30",
        "hearings_so_far": 4,
        "num_parties": 3,
        "is_appeal": 0,
        "court": "Delhi High Court",
    },
    {
        "case_no": "CON/2023/007",
        "title": "Meera v. Reliance Insurance (Consumer)",
        "description": "Consumer complaint against insurance company for deficiency in service.",
        "case_type": "Consumer",
        "filing_date": "2023-05-15",
        "hearings_so_far": 9,
        "num_parties": 2,
        "is_appeal": 0,
        "court": "NCDRC",
    },
    {
        "case_no": "CRL/2024/008",
        "title": "Deepak v. State (Cheque Bounce Appeal)",
        "description": "Appeal against conviction under Section 138 NI Act for dishonour of cheque.",
        "case_type": "Criminal",
        "filing_date": "2024-02-20",
        "hearings_so_far": 2,
        "num_parties": 2,
        "is_appeal": 1,
        "court": "Delhi High Court",
    },
    {
        "case_no": "PRO/2023/009",
        "title": "Landlord Kapoor v. Tenant Singh (Eviction)",
        "description": "Eviction petition under Delhi Rent Control Act for arrears of rent.",
        "case_type": "Property/Civil",
        "filing_date": "2023-09-01",
        "hearings_so_far": 11,
        "num_parties": 2,
        "is_appeal": 0,
        "court": "Rent Controller Delhi",
    },
    {
        "case_no": "CRL/2023/010",
        "title": "State v. Gang of Five (NDPS)",
        "description": "Criminal trial for possession and trafficking of narcotics under NDPS Act.",
        "case_type": "Criminal",
        "filing_date": "2023-04-10",
        "hearings_so_far": 15,
        "num_parties": 5,
        "is_appeal": 0,
        "court": "Special NDPS Court Mumbai",
    },
    {
        "case_no": "LAB/2023/011",
        "title": "Workers Union v. Textile Mill (Closure)",
        "description": "Industrial dispute challenging factory closure and seeking reinstatement of 200 workmen.",
        "case_type": "Labour",
        "filing_date": "2023-12-05",
        "hearings_so_far": 6,
        "num_parties": 4,
        "is_appeal": 0,
        "court": "Industrial Tribunal Chennai",
    },
    {
        "case_no": "FAM/2024/012",
        "title": "Suresh v. Meena (Maintenance)",
        "description": "Application for maintenance under Section 125 CrPC by wife and minor children.",
        "case_type": "Family",
        "filing_date": "2024-04-01",
        "hearings_so_far": 1,
        "num_parties": 2,
        "is_appeal": 0,
        "court": "Family Court Jaipur",
    },
]

# ─────────────────────────────────────────────
# Main seeding logic
# ─────────────────────────────────────────────

def main():
    print(f"Initialising database at {DB_PATH} ...")
    conn = sqlite3.connect(str(DB_PATH))
    init_db(conn)

    # Write JSON files and insert judgments
    print(f"\nSeeding judgments ({len(JUDGMENTS)} total) ...")
    for j in JUDGMENTS:
        filepath = JUDGMENTS_DIR / f"{j['id']}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "id": j["id"],
                "title": j["title"],
                "court": j["court"],
                "year": j["year"],
                "case_type": j["case_type"],
                "text": j["text"],
            }, f, indent=2, ensure_ascii=False)
        # Insert into DB (upsert)
        conn.execute(
            """INSERT OR REPLACE INTO judgments
               (id, title, court, year, case_type, text_content)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (j["id"], j["title"], j["court"], j["year"], j["case_type"], j["text"]),
        )
        print(f"  [judgment] {j['id']}: {j['title'][:60]}")

    conn.commit()
    print(f"\nSeeding pending cases ({len(PENDING_CASES)}) ...")
    for pc in PENDING_CASES:
        conn.execute(
            """INSERT OR REPLACE INTO pending_cases
               (case_no, title, description, case_type, filing_date,
                hearings_so_far, num_parties, is_appeal, court)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pc["case_no"], pc["title"], pc["description"], pc["case_type"],
                pc["filing_date"], pc["hearings_so_far"], pc["num_parties"],
                pc["is_appeal"], pc["court"],
            ),
        )
        print(f"  [pending]  {pc['case_no']}: {pc['title'][:60]}")

    conn.commit()
    conn.close()

    print(f"\nSeeding complete: {len(JUDGMENTS)} judgments, {len(PENDING_CASES)} pending cases")


if __name__ == "__main__":
    main()
