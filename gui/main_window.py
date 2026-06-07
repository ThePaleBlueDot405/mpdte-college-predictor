"""
MPDTE College Predictor - Main GUI Application
Built with CustomTkinter for modern dark UI
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import logging
import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import init_db, get_db_stats, get_all_branches, get_analytics, get_imported_pdfs
from core.pdf_extractor import extract_pdf, extract_round_year, get_branch_full_name
from core.database import insert_records, search_records, get_college_detail, delete_pdf_records
from core.prediction_engine import (
    predict_colleges, generate_counselling_strategy, simulate_rank,
    get_best_options, generate_summary, get_missed_opportunities, BRANCH_GROUPS
)
from core.export_manager import export_csv, export_excel, export_pdf_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Theme ────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "bg_dark": "#0d1117",
    "bg_card": "#161b22",
    "bg_input": "#21262d",
    "accent_blue": "#1f6feb",
    "accent_green": "#238636",
    "accent_red": "#da3633",
    "accent_yellow": "#d29922",
    "accent_purple": "#8b5cf6",
    "text_primary": "#c9d1d9",
    "text_secondary": "#8b949e",
    "border": "#30363d",
    "highlight": "#388bfd",
}

BAND_COLORS_HEX = {
    "Extremely Likely":       "#00C851",
    "Likely":                 "#7CB342",
    "Reasonable":             "#FFD600",
    "Borderline":             "#FF6D00",
    "Stretch":                "#D32F2F",
    "Historically Unavailable": "#880E4F",
}
# Legacy alias kept for any remaining references
RISK_COLORS = BAND_COLORS_HEX


class MPDTEApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MPDTE College Predictor & Analyzer")
        self.geometry("1400x900")
        self.minsize(1200, 750)
        self.configure(fg_color=COLORS["bg_dark"])

        # State
        self._last_results = []
        self._last_summary = {}
        self._selected_branches = []

        # Initialize DB
        init_db()

        self._build_ui()
        self._refresh_stats()

    # ── UI Build ─────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Top header
        self._build_header()

        # Main layout: sidebar + content
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.main_frame.grid_columnconfigure(1, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        # Sidebar
        self._build_sidebar()

        # Content area with tabs
        self.content = ctk.CTkFrame(self.main_frame, fg_color=COLORS["bg_card"],
                                     corner_radius=12, border_width=1,
                                     border_color=COLORS["border"])
        self.content.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        # Tab view
        self.tabs = ctk.CTkTabview(self.content, fg_color="transparent",
                                    segmented_button_selected_color=COLORS["accent_blue"],
                                    segmented_button_fg_color=COLORS["bg_dark"])
        self.tabs.pack(fill="both", expand=True, padx=5, pady=5)

        # Add tabs
        tabs_list = [
            "🎯 What Can I Get?",
            "📊 Results",
            "📋 Strategy",
            "🔍 Search",
            "📈 Analytics",
            "📁 Import PDF",
            "🏫 College Detail",
        ]
        for t in tabs_list:
            self.tabs.add(t)

        self._build_predict_tab()
        self._build_results_tab()
        self._build_strategy_tab()
        self._build_search_tab()
        self._build_analytics_tab()
        self._build_import_tab()
        self._build_college_tab()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], height=60,
                               corner_radius=0, border_width=0)
        header.pack(fill="x", padx=0, pady=0)

        ctk.CTkLabel(
            header,
            text="⚡ MPDTE College Predictor & Analyzer",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["accent_blue"]
        ).pack(side="left", padx=20, pady=15)

        self.stats_label = ctk.CTkLabel(
            header, text="",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_secondary"]
        )
        self.stats_label.pack(side="right", padx=20)

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self.main_frame, fg_color=COLORS["bg_card"],
                                width=280, corner_radius=12,
                                border_width=1, border_color=COLORS["border"])
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        # Title
        ctk.CTkLabel(sidebar, text="Your Profile",
                      font=ctk.CTkFont(size=14, weight="bold"),
                      text_color=COLORS["text_primary"]).pack(pady=(15, 8), padx=15)

        # JEE Rank
        self._sidebar_label(sidebar, "JEE Rank")
        self.rank_var = ctk.StringVar(value="")
        self.rank_entry = ctk.CTkEntry(
            sidebar, textvariable=self.rank_var, placeholder_text="e.g. 450000",
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            width=240, height=36, font=ctk.CTkFont(size=14)
        )
        self.rank_entry.pack(padx=15, pady=(0, 8))

        # Category
        self._sidebar_label(sidebar, "Category")
        self.cat_var = ctk.StringVar(value="General (UR)")
        self.cat_menu = ctk.CTkOptionMenu(
            sidebar, variable=self.cat_var,
            values=["General (UR)", "OBC", "SC", "ST", "EWS"],
            fg_color=COLORS["bg_input"], button_color=COLORS["accent_blue"],
            width=240, height=36
        )
        self.cat_menu.pack(padx=15, pady=(0, 8))

        # MP Domicile
        self._sidebar_label(sidebar, "MP Domicile")
        self.domicile_var = ctk.StringVar(value="Yes")
        dom_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        dom_frame.pack(padx=15, pady=(0, 8), fill="x")
        for val in ["Yes", "No"]:
            ctk.CTkRadioButton(
                dom_frame, text=val, variable=self.domicile_var, value=val,
                fg_color=COLORS["accent_blue"], hover_color=COLORS["highlight"]
            ).pack(side="left", padx=10)

        # Fee Waiver
        self._sidebar_label(sidebar, "Fee Waiver (FW)")
        self.fw_var = ctk.BooleanVar(value=False)
        fw_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        fw_frame.pack(padx=15, pady=(0, 8), fill="x")
        for lbl, val in [("Yes", True), ("No", False)]:
            ctk.CTkRadioButton(
                fw_frame, text=lbl,
                variable=self.fw_var, value=val,
                fg_color=COLORS["accent_blue"], hover_color=COLORS["highlight"]
            ).pack(side="left", padx=10)

        # Gender
        self._sidebar_label(sidebar, "Gender")
        self.gender_var = ctk.StringVar(value="Male")
        gen_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        gen_frame.pack(padx=15, pady=(0, 12), fill="x")
        for g in ["Male", "Female"]:
            ctk.CTkRadioButton(
                gen_frame, text=g, variable=self.gender_var, value=g,
                fg_color=COLORS["accent_blue"]
            ).pack(side="left", padx=10)

        # Separator
        ctk.CTkFrame(sidebar, height=1, fg_color=COLORS["border"]).pack(fill="x", padx=10, pady=5)

        # Branch Groups
        ctk.CTkLabel(sidebar, text="Branch Groups",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      text_color=COLORS["text_secondary"]).pack(pady=(5, 4), padx=15)

        group_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        group_frame.pack(padx=10, pady=(0, 5), fill="x")

        groups = [
            ("💻 CS Related", "Computer Science Related"),
            ("💡 CS + ECE", "Computer Science + Electronics"),
            ("⚙️ Core Engg", "Core Engineering"),
            ("🌐 All Branches", "All Branches"),
        ]
        for i, (lbl, grp) in enumerate(groups):
            btn = ctk.CTkButton(
                group_frame, text=lbl, height=30,
                fg_color=COLORS["bg_input"], hover_color=COLORS["accent_blue"],
                text_color=COLORS["text_primary"], font=ctk.CTkFont(size=11),
                corner_radius=6,
                command=lambda g=grp: self._select_branch_group(g)
            )
            btn.grid(row=i // 2, column=i % 2, padx=3, pady=3, sticky="ew")
        group_frame.grid_columnconfigure(0, weight=1)
        group_frame.grid_columnconfigure(1, weight=1)

        # Prediction thresholds
        ctk.CTkFrame(sidebar, height=1, fg_color=COLORS["border"]).pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(sidebar, text="Probability Thresholds",
                      font=ctk.CTkFont(size=11, weight="bold"),
                      text_color=COLORS["text_secondary"]).pack(pady=(3, 2))

        thresh_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        thresh_frame.pack(padx=10, fill="x")

        self.dream_var = ctk.StringVar(value="10")
        self.safe_var = ctk.StringVar(value="25")
        self.vsafe_var = ctk.StringVar(value="50")

        for lbl, var in [("Dream %", self.dream_var), ("Safe %", self.safe_var), ("VSafe %", self.vsafe_var)]:
            row = ctk.CTkFrame(thresh_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=lbl, width=60, font=ctk.CTkFont(size=10),
                          text_color=COLORS["text_secondary"]).pack(side="left")
            ctk.CTkEntry(row, textvariable=var, width=50, height=24,
                          fg_color=COLORS["bg_input"]).pack(side="right")

        # ANALYZE button
        ctk.CTkFrame(sidebar, height=1, fg_color=COLORS["border"]).pack(fill="x", padx=10, pady=8)
        self.analyze_btn = ctk.CTkButton(
            sidebar, text="🔍 ANALYZE MY CHANCES",
            command=self._run_analysis,
            fg_color=COLORS["accent_blue"],
            hover_color=COLORS["highlight"],
            height=44, font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=8
        )
        self.analyze_btn.pack(padx=15, pady=(0, 8), fill="x")

        # Quick buttons
        quick_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        quick_frame.pack(padx=10, fill="x")
        for i, (lbl, ft) in enumerate([
            ("🎓 Best CS", "cs"), ("⚙️ Best Core", "core"),
            ("🏛️ Govt Only", "govt"), ("💰 Fee Waiver", "fw"),
        ]):
            ctk.CTkButton(
                quick_frame, text=lbl, height=28,
                fg_color=COLORS["bg_input"], hover_color=COLORS["accent_green"],
                font=ctk.CTkFont(size=10), corner_radius=6,
                command=lambda f=ft: self._quick_filter(f)
            ).grid(row=i // 2, column=i % 2, padx=3, pady=2, sticky="ew")
        quick_frame.grid_columnconfigure(0, weight=1)
        quick_frame.grid_columnconfigure(1, weight=1)

    def _sidebar_label(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=11),
                      text_color=COLORS["text_secondary"]).pack(anchor="w", padx=15, pady=(4, 2))

    # ── Tab: What Can I Get? (Predict) ───────────────────────────────────────
    def _build_predict_tab(self):
        tab = self.tabs.tab("🎯 What Can I Get?")

        # Branch selection area
        top = ctk.CTkFrame(tab, fg_color=COLORS["bg_dark"], corner_radius=10)
        top.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(top, text="Select Branch Preferences",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      text_color=COLORS["text_primary"]).pack(anchor="w", padx=12, pady=(10, 5))

        # Branch checkboxes with scrollable frame
        branch_scroll = ctk.CTkScrollableFrame(top, height=180, fg_color=COLORS["bg_input"],
                                                corner_radius=8)
        branch_scroll.pack(fill="x", padx=12, pady=(0, 10))

        self.branch_vars = {}
        self._populate_branch_checkboxes(branch_scroll)

        # Selected branches display
        self.selected_label = ctk.CTkLabel(
            tab, text="No branches selected (will search all)",
            font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"]
        )
        self.selected_label.pack(anchor="w", padx=22, pady=(0, 5))

        # ── Rank Simulator ───────────────────────────────────────────────────
        sim_frame = ctk.CTkFrame(tab, fg_color=COLORS["bg_dark"], corner_radius=10)
        sim_frame.pack(fill="x", padx=10, pady=(0, 8))

        ctk.CTkLabel(sim_frame, text="🎲 Rank Simulator — How do results change at different ranks?",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      text_color=COLORS["text_primary"]).pack(anchor="w", padx=12, pady=(8, 4))

        sim_inner = ctk.CTkFrame(sim_frame, fg_color="transparent")
        sim_inner.pack(fill="x", padx=12, pady=(0, 4))

        ctk.CTkLabel(sim_inner, text="Test ranks:",
                      text_color=COLORS["text_secondary"],
                      font=ctk.CTkFont(size=11)).pack(side="left", padx=5)

        self.sim_vars = []
        for hint in ["350000", "300000", "250000"]:
            v = ctk.StringVar(value=hint)
            self.sim_vars.append(v)
            ctk.CTkEntry(sim_inner, textvariable=v, width=90, height=28,
                          fg_color=COLORS["bg_input"]).pack(side="left", padx=4)

        ctk.CTkButton(sim_inner, text="Simulate", height=28,
                       fg_color=COLORS["accent_purple"], hover_color="#7c3aed",
                       command=self._run_simulator,
                       font=ctk.CTkFont(size=11)).pack(side="left", padx=8)

        self.sim_result_label = ctk.CTkLabel(
            sim_frame, text="",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=11),
            wraplength=900, justify="left"
        )
        self.sim_result_label.pack(anchor="w", padx=12, pady=(0, 8))

        # ── Rank Range Analysis ─────────────────────────────────────────────
        range_frame = ctk.CTkFrame(tab, fg_color=COLORS["bg_dark"], corner_radius=10)
        range_frame.pack(fill="x", padx=10, pady=(0, 8))

        range_header = ctk.CTkFrame(range_frame, fg_color="transparent")
        range_header.pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkLabel(range_header, text="📊 Rank Uncertainty Analysis — Best/Expected/Worst Case",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      text_color=COLORS["text_primary"]).pack(side="left")

        range_ctrl = ctk.CTkFrame(range_frame, fg_color="transparent")
        range_ctrl.pack(fill="x", padx=12, pady=(0, 4))

        ctk.CTkLabel(range_ctrl, text="Margin ±:",
                      text_color=COLORS["text_secondary"],
                      font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 6))

        self.range_margin_var = ctk.StringVar(value="25000")
        for m in ["5000", "10000", "25000", "50000", "100000"]:
            ctk.CTkRadioButton(
                range_ctrl, text=f"±{int(m)//1000}k", variable=self.range_margin_var, value=m,
                fg_color=COLORS["accent_blue"], font=ctk.CTkFont(size=10),
                command=self._run_range_analysis
            ).pack(side="left", padx=6)

        ctk.CTkButton(range_ctrl, text="Analyze Range", height=28,
                       fg_color=COLORS["bg_input"], hover_color=COLORS["accent_blue"],
                       command=self._run_range_analysis,
                       font=ctk.CTkFont(size=11)).pack(side="left", padx=10)

        self.range_result_label = ctk.CTkLabel(
            range_frame, text="Click 'Analyze Range' to see best/expected/worst case options.",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=11),
            wraplength=900, justify="left"
        )
        self.range_result_label.pack(anchor="w", padx=12, pady=(0, 8))

        # ── Missed Opportunities ────────────────────────────────────────────
        missed_frame = ctk.CTkFrame(tab, fg_color=COLORS["bg_dark"], corner_radius=10)
        missed_frame.pack(fill="x", padx=10, pady=(0, 8))

        header_row = ctk.CTkFrame(missed_frame, fg_color="transparent")
        header_row.pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkLabel(header_row, text="⚡ Colleges Missed by Small Margin (Borderline options)",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      text_color=COLORS["accent_yellow"]).pack(side="left")
        ctk.CTkButton(header_row, text="Find Missed",
                       height=26, fg_color=COLORS["accent_yellow"],
                       text_color="#000000", hover_color="#b7791f",
                       font=ctk.CTkFont(size=10),
                       command=self._find_missed).pack(side="right")

        self.missed_label = ctk.CTkLabel(
            missed_frame, text="Click 'Find Missed' after entering your rank",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=11),
            wraplength=900, justify="left"
        )
        self.missed_label.pack(anchor="w", padx=12, pady=(0, 8))

        # ── Diagnostics Panel ───────────────────────────────────────────────
        diag_frame = ctk.CTkFrame(tab, fg_color=COLORS["bg_dark"], corner_radius=10)
        diag_frame.pack(fill="x", padx=10, pady=(0, 8))

        diag_header = ctk.CTkFrame(diag_frame, fg_color="transparent")
        diag_header.pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkLabel(diag_header, text="🔬 Prediction Diagnostics — Top 5 results",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      text_color=COLORS["text_secondary"]).pack(side="left")
        ctk.CTkButton(diag_header, text="Show Diagnostics", height=26,
                       fg_color=COLORS["bg_input"], hover_color=COLORS["accent_blue"],
                       font=ctk.CTkFont(size=10),
                       command=self._show_diagnostics).pack(side="right")

        self.diag_text = ctk.CTkTextbox(
            diag_frame, height=130, fg_color=COLORS["bg_input"],
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color=COLORS["text_secondary"]
        )
        self.diag_text.pack(fill="x", padx=12, pady=(0, 8))
        self.diag_text.insert("end",
            "  College                              Branch        Open Rank  Close Rank  Dist↑Open  Dist↑Close  Band\n"
            "  Press 'Show Diagnostics' after running analysis.\n"
        )
        self.diag_text.configure(state="disabled")

        # Status
        self.predict_status = ctk.CTkLabel(
            tab, text="Enter your rank and click ANALYZE MY CHANCES →",
            font=ctk.CTkFont(size=12), text_color=COLORS["accent_blue"]
        )
        self.predict_status.pack(pady=10)

    def _populate_branch_checkboxes(self, parent):
        """Populate branch checkboxes from DB"""
        branches = get_all_branches()
        if not branches:
            ctk.CTkLabel(parent, text="No branches in database. Import PDFs first.",
                          text_color=COLORS["text_secondary"]).pack()
            return

        cols = 3
        for i, b in enumerate(branches):
            name = b["branch_full_name"] or b["branch_code"]
            if not name:
                continue
            var = ctk.BooleanVar(value=False)
            self.branch_vars[name] = var
            cb = ctk.CTkCheckBox(
                parent, text=name[:55], variable=var,
                fg_color=COLORS["accent_blue"], hover_color=COLORS["highlight"],
                font=ctk.CTkFont(size=10), text_color=COLORS["text_primary"],
                command=self._update_selected_branches
            )
            cb.grid(row=i // cols, column=i % cols, sticky="w", padx=8, pady=2)

        for c in range(cols):
            parent.grid_columnconfigure(c, weight=1)

    def _update_selected_branches(self):
        selected = [name for name, var in self.branch_vars.items() if var.get()]
        self._selected_branches = selected
        if selected:
            self.selected_label.configure(
                text=f"✅ {len(selected)} branch(es) selected",
                text_color=COLORS["accent_green"]
            )
        else:
            self.selected_label.configure(
                text="No branches selected (will search all)",
                text_color=COLORS["text_secondary"]
            )

    def _select_branch_group(self, group_name: str):
        branches_in_group = BRANCH_GROUPS.get(group_name, [])

        # Uncheck all first
        for var in self.branch_vars.values():
            var.set(False)

        if group_name == "All Branches":
            for var in self.branch_vars.values():
                var.set(True)
        else:
            for name, var in self.branch_vars.items():
                if name in branches_in_group:
                    var.set(True)

        self._update_selected_branches()

    # ── Tab: Results ─────────────────────────────────────────────────────────
    def _build_results_tab(self):
        tab = self.tabs.tab("📊 Results")

        # Summary bar
        self.result_summary_frame = ctk.CTkFrame(tab, fg_color=COLORS["bg_dark"],
                                                   corner_radius=8, height=60)
        self.result_summary_frame.pack(fill="x", padx=10, pady=(10, 5))
        self.result_summary_frame.pack_propagate(False)

        self.result_summary_labels = {}
        for key, color in [
            ("Colleges", "#8b949e"),
            ("Extremely Likely", "#00C851"),
            ("Likely", "#7CB342"),
            ("Reasonable", "#FFD600"),
            ("Borderline", "#FF6D00"),
            ("Stretch", "#D32F2F"),
        ]:
            col = ctk.CTkFrame(self.result_summary_frame, fg_color="transparent")
            col.pack(side="left", padx=15, pady=5)
            ctk.CTkLabel(col, text=key, font=ctk.CTkFont(size=9),
                          text_color="#8b949e").pack()
            lbl = ctk.CTkLabel(col, text="0", font=ctk.CTkFont(size=16, weight="bold"),
                                text_color=color)
            lbl.pack()
            self.result_summary_labels[key] = lbl

        # Filter bar
        filter_bar = ctk.CTkFrame(tab, fg_color="transparent")
        filter_bar.pack(fill="x", padx=10, pady=(0, 5))

        ctk.CTkLabel(filter_bar, text="Show:",
                      text_color=COLORS["text_secondary"],
                      font=ctk.CTkFont(size=11)).pack(side="left", padx=5)

        self.result_filter_var = ctk.StringVar(value="All")
        for opt in ["All", "Extremely Likely", "Likely", "Reasonable", "Borderline"]:
            ctk.CTkRadioButton(
                filter_bar, text=opt, variable=self.result_filter_var, value=opt,
                fg_color=COLORS["accent_blue"],
                font=ctk.CTkFont(size=10),
                command=self._apply_result_filter
            ).pack(side="left", padx=8)

        # Sort
        ctk.CTkLabel(filter_bar, text="Sort:",
                      text_color=COLORS["text_secondary"],
                      font=ctk.CTkFont(size=11)).pack(side="left", padx=(20, 5))
        self.sort_var = ctk.StringVar(value="Probability")
        sort_menu = ctk.CTkOptionMenu(
            filter_bar, variable=self.sort_var,
            values=["Probability", "Closing Rank", "College Name", "Branch"],
            fg_color=COLORS["bg_input"], button_color=COLORS["accent_blue"],
            width=130, height=28,
            command=lambda _: self._apply_result_filter()
        )
        sort_menu.pack(side="left", padx=5)

        # Export buttons
        for lbl, fn in [("📄 CSV", self._export_csv), ("📊 Excel", self._export_excel),
                          ("📝 PDF Report", self._export_pdf)]:
            ctk.CTkButton(filter_bar, text=lbl, height=28, width=90,
                           fg_color=COLORS["bg_input"], hover_color=COLORS["accent_green"],
                           font=ctk.CTkFont(size=10),
                           command=fn).pack(side="right", padx=3)

        # Results table
        self.results_table = self._make_treeview(
            tab,
            columns=["College", "Branch", "Type", "Open Rank", "Close Rank",
                      "Category", "FW", "Band", "Explanation"],
            widths=[220, 200, 70, 90, 90, 120, 40, 160, 260],
        )
        self.results_table.bind("<Double-1>", self._on_result_double_click)

    def _make_treeview(self, parent, columns, widths):
        frame = ctk.CTkFrame(parent, fg_color=COLORS["bg_dark"], corner_radius=8)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Custom.Treeview",
                         background=COLORS["bg_dark"],
                         foreground=COLORS["text_primary"],
                         fieldbackground=COLORS["bg_dark"],
                         rowheight=28,
                         font=("Helvetica", 10))
        style.configure("Custom.Treeview.Heading",
                         background=COLORS["bg_card"],
                         foreground=COLORS["text_primary"],
                         font=("Helvetica", 10, "bold"))
        style.map("Custom.Treeview",
                   background=[("selected", COLORS["accent_blue"])],
                   foreground=[("selected", "white")])

        vsb = ttk.Scrollbar(frame, orient="vertical")
        hsb = ttk.Scrollbar(frame, orient="horizontal")

        tree = ttk.Treeview(
            frame, columns=columns, show="headings",
            style="Custom.Treeview",
            yscrollcommand=vsb.set, xscrollcommand=hsb.set
        )
        vsb.configure(command=tree.yview)
        hsb.configure(command=tree.xview)

        for col, w in zip(columns, widths):
            tree.heading(col, text=col,
                          command=lambda c=col, t=tree: self._sort_tree(t, c))
            tree.column(col, width=w, minwidth=40, anchor="w")

        tree.tag_configure("extremely_likely",        background="#003300", foreground="#00ff88")
        tree.tag_configure("likely",                   background="#1a3300", foreground="#7CB342")
        tree.tag_configure("reasonable",               background="#332200", foreground="#FFD600")
        tree.tag_configure("borderline",               background="#331500", foreground="#FF6D00")
        tree.tag_configure("stretch",                  background="#330000", foreground="#D32F2F")
        tree.tag_configure("historically_unavailable", background="#1a001a", foreground="#880E4F")
        tree.tag_configure("alt", background="#1a1f26")

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        tree.pack(fill="both", expand=True)

        return tree

    def _sort_tree(self, tree, col):
        """Sort treeview by column"""
        data = [(tree.set(child, col), child) for child in tree.get_children("")]
        try:
            data.sort(key=lambda x: float(x[0].replace("%", "").replace(",", "")))
        except Exception:
            data.sort(key=lambda x: x[0].lower())
        for i, (_, child) in enumerate(data):
            tree.move(child, "", i)

    # ── Tab: Strategy ─────────────────────────────────────────────────────────
    def _build_strategy_tab(self):
        tab = self.tabs.tab("📋 Strategy")

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(top, text="🎯 Counselling Preference Order",
                      font=ctk.CTkFont(size=14, weight="bold"),
                      text_color=COLORS["text_primary"]).pack(side="left")

        ctk.CTkButton(top, text="Generate Strategy",
                       fg_color=COLORS["accent_purple"], hover_color="#7c3aed",
                       height=32, command=self._generate_strategy).pack(side="right", padx=5)

        self.strategy_label = ctk.CTkLabel(
            tab, text="Click 'Generate Strategy' after analysis",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=11)
        )
        self.strategy_label.pack(pady=5)

        self.strategy_table = self._make_treeview(
            tab,
            columns=["#", "College", "Branch", "Type", "Close Rank", "Band", "Score"],
            widths=[35, 230, 200, 70, 100, 160, 65]
            
        )

    # ── Tab: Search ───────────────────────────────────────────────────────────
    def _build_search_tab(self):
        tab = self.tabs.tab("🔍 Search")

        search_bar = ctk.CTkFrame(tab, fg_color="transparent")
        search_bar.pack(fill="x", padx=10, pady=10)

        self.search_var = ctk.StringVar()
        self.search_var.trace("w", lambda *_: self._do_search())

        ctk.CTkEntry(
            search_bar, textvariable=self.search_var,
            placeholder_text="Search colleges, branches, cities, categories...",
            fg_color=COLORS["bg_input"], border_color=COLORS["accent_blue"],
            height=40, font=ctk.CTkFont(size=13), width=400
        ).pack(side="left", padx=5)

        # Filters
        self.filter_type_var = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(
            search_bar, variable=self.filter_type_var,
            values=["All", "GOVT", "AIDED", "private", "S.F.I."],
            fg_color=COLORS["bg_input"], button_color=COLORS["accent_blue"],
            width=110, height=40, command=lambda _: self._do_search()
        ).pack(side="left", padx=5)

        self.filter_fw_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(search_bar, text="Fee Waiver Only",
                         variable=self.filter_fw_var,
                         fg_color=COLORS["accent_blue"],
                         command=self._do_search).pack(side="left", padx=10)

        self.search_count_label = ctk.CTkLabel(
            search_bar, text="", text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(size=11)
        )
        self.search_count_label.pack(side="right", padx=10)

        self.search_table = self._make_treeview(
            tab,
            columns=["College", "Branch", "Type", "FW", "Open Rank", "Close Rank", "Category", "Domicile", "City"],
            widths=[230, 190, 70, 40, 90, 90, 120, 80, 90],
        )
        self.search_table.bind("<Double-1>", self._on_search_double_click)

    # ── Tab: Analytics ────────────────────────────────────────────────────────
    def _build_analytics_tab(self):
        tab = self.tabs.tab("📈 Analytics")

        # Stats grid
        stats_frame = ctk.CTkFrame(tab, fg_color=COLORS["bg_dark"], corner_radius=10)
        stats_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(stats_frame, text="Database Statistics",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      text_color=COLORS["text_primary"]).pack(anchor="w", padx=15, pady=(10, 5))

        self.analytics_stats_frame = ctk.CTkFrame(stats_frame, fg_color="transparent")
        self.analytics_stats_frame.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkButton(
            tab, text="🔄 Refresh Analytics",
            fg_color=COLORS["accent_blue"], hover_color=COLORS["highlight"],
            height=32, command=self._load_analytics
        ).pack(anchor="e", padx=10)

        # Charts area (using text-based charts since matplotlib would need display)
        self.analytics_scroll = ctk.CTkScrollableFrame(tab, fg_color=COLORS["bg_dark"],
                                                         corner_radius=8)
        self.analytics_scroll.pack(fill="both", expand=True, padx=10, pady=(5, 10))

    def _load_analytics(self):
        """Load and display analytics"""
        try:
            data = get_analytics()
            stats = get_db_stats()

            # Clear
            for w in self.analytics_stats_frame.winfo_children():
                w.destroy()
            for w in self.analytics_scroll.winfo_children():
                w.destroy()

            # Stat cards
            stat_items = [
                ("📊 Records", f"{stats['total_records']:,}", COLORS["accent_blue"]),
                ("🏫 Colleges", f"{stats['total_colleges']:,}", COLORS["accent_green"]),
                ("📚 Branches", f"{stats['total_branches']:,}", COLORS["accent_purple"]),
                ("📁 PDFs", f"{stats['total_pdfs']:,}", COLORS["accent_yellow"]),
                ("📈 Max Rank", f"{data.get('max_closing_rank', 0) or 0:,}", COLORS["accent_red"]),
                ("📉 Min Rank", f"{data.get('min_closing_rank', 0) or 0:,}", "#00C851"),
            ]
            for i, (lbl, val, color) in enumerate(stat_items):
                card = ctk.CTkFrame(self.analytics_stats_frame, fg_color=COLORS["bg_card"],
                                     corner_radius=8, border_width=1, border_color=COLORS["border"])
                card.grid(row=0, column=i, padx=6, pady=5, sticky="ew")
                ctk.CTkLabel(card, text=lbl, font=ctk.CTkFont(size=10),
                              text_color=COLORS["text_secondary"]).pack(pady=(8, 2))
                ctk.CTkLabel(card, text=val, font=ctk.CTkFont(size=18, weight="bold"),
                              text_color=color).pack(pady=(0, 8))

            for i in range(6):
                self.analytics_stats_frame.grid_columnconfigure(i, weight=1)

            # Category distribution
            self._make_bar_chart(
                self.analytics_scroll, "Category Distribution",
                data.get("category_distribution", [])[:12]
            )
            # Branch distribution
            self._make_bar_chart(
                self.analytics_scroll, "Top Branches",
                data.get("branch_distribution", [])[:10]
            )
            # College type
            self._make_bar_chart(
                self.analytics_scroll, "College Types",
                data.get("college_type_distribution", [])
            )

        except Exception as e:
            logger.error(f"Analytics error: {e}")

    def _make_bar_chart(self, parent, title, data):
        """Text-based bar chart"""
        if not data:
            return

        frame = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=8,
                               border_width=1, border_color=COLORS["border"])
        frame.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(frame, text=title,
                      font=ctk.CTkFont(size=12, weight="bold"),
                      text_color=COLORS["text_primary"]).pack(anchor="w", padx=12, pady=(8, 5))

        max_val = max((v for _, v in data), default=1)
        colors_cycle = [COLORS["accent_blue"], COLORS["accent_green"],
                         COLORS["accent_purple"], COLORS["accent_yellow"]]

        for i, (label, value) in enumerate(data):
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)

            lbl_text = str(label)[:35] if label else "Unknown"
            ctk.CTkLabel(row, text=lbl_text, width=200, anchor="w",
                          font=ctk.CTkFont(size=10),
                          text_color=COLORS["text_secondary"]).pack(side="left")

            bar_width = max(int((value / max_val) * 300), 5)
            bar = ctk.CTkFrame(row, width=bar_width, height=16,
                                fg_color=colors_cycle[i % len(colors_cycle)],
                                corner_radius=4)
            bar.pack(side="left", padx=5)

            ctk.CTkLabel(row, text=f"{value:,}",
                          font=ctk.CTkFont(size=10),
                          text_color=COLORS["text_secondary"]).pack(side="left", padx=5)

        ctk.CTkFrame(frame, height=8, fg_color="transparent").pack()

    # ── Tab: Import PDF ───────────────────────────────────────────────────────
    def _build_import_tab(self):
        tab = self.tabs.tab("📁 Import PDF")

        # Import area
        import_frame = ctk.CTkFrame(tab, fg_color=COLORS["bg_dark"], corner_radius=10)
        import_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(import_frame, text="Import MPDTE Counselling PDFs",
                      font=ctk.CTkFont(size=14, weight="bold"),
                      text_color=COLORS["text_primary"]).pack(anchor="w", padx=15, pady=(12, 5))

        ctk.CTkLabel(import_frame,
                      text="Select one or more MPDTE counselling PDFs to extract and store data automatically.",
                      text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=11)).pack(anchor="w", padx=15)

        btn_row = ctk.CTkFrame(import_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=12)

        ctk.CTkButton(
            btn_row, text="📂 Select PDF Files",
            fg_color=COLORS["accent_blue"], hover_color=COLORS["highlight"],
            height=40, font=ctk.CTkFont(size=13),
            command=self._import_pdfs
        ).pack(side="left", padx=(0, 10))

        self.import_status = ctk.CTkLabel(
            btn_row, text="No PDFs imported yet",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=11)
        )
        self.import_status.pack(side="left")

        # Progress
        self.import_progress = ctk.CTkProgressBar(import_frame, width=400, height=12,
                                                    fg_color=COLORS["bg_input"],
                                                    progress_color=COLORS["accent_green"])
        self.import_progress.pack(padx=15, pady=(0, 5))
        self.import_progress.set(0)

        self.import_detail = ctk.CTkLabel(
            import_frame, text="",
            text_color=COLORS["accent_green"], font=ctk.CTkFont(size=11)
        )
        self.import_detail.pack(anchor="w", padx=15, pady=(0, 12))

        # Imported PDFs list
        ctk.CTkLabel(tab, text="Imported PDFs",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      text_color=COLORS["text_primary"]).pack(anchor="w", padx=15, pady=(5, 5))

        self.pdf_list_frame = ctk.CTkScrollableFrame(tab, fg_color=COLORS["bg_dark"],
                                                      corner_radius=8, height=300)
        self.pdf_list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._refresh_pdf_list()

    def _refresh_pdf_list(self):
        for w in self.pdf_list_frame.winfo_children():
            w.destroy()

        pdfs = get_imported_pdfs()
        if not pdfs:
            ctk.CTkLabel(self.pdf_list_frame,
                          text="No PDFs imported yet. Click 'Select PDF Files' to get started.",
                          text_color=COLORS["text_secondary"]).pack(pady=20)
            return

        for pdf in pdfs:
            row = ctk.CTkFrame(self.pdf_list_frame, fg_color=COLORS["bg_card"],
                                corner_radius=6, border_width=1, border_color=COLORS["border"])
            row.pack(fill="x", padx=5, pady=3)

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, padx=10, pady=8)

            ctk.CTkLabel(info, text=f"📄 {pdf['filename']}",
                          font=ctk.CTkFont(size=11, weight="bold"),
                          text_color=COLORS["text_primary"]).pack(anchor="w")
            ctk.CTkLabel(
                info,
                text=f"Imported: {pdf['import_date'][:16]} | "
                     f"Records: {pdf['records_imported']:,} | "
                     f"Duplicates: {pdf['duplicates_skipped']} | "
                     f"Round: {pdf.get('round_info', 'N/A')} | Year: {pdf.get('year', 'N/A')}",
                font=ctk.CTkFont(size=10), text_color=COLORS["text_secondary"]
            ).pack(anchor="w")

            ctk.CTkButton(
                row, text="🗑️", width=30, height=30,
                fg_color=COLORS["accent_red"], hover_color="#b91c1c",
                command=lambda p=pdf["filename"]: self._delete_pdf(p)
            ).pack(side="right", padx=8)

    # ── Tab: College Detail ───────────────────────────────────────────────────
    def _build_college_tab(self):
        tab = self.tabs.tab("🏫 College Detail")

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=10)

        self.college_search_var = ctk.StringVar()
        ctk.CTkEntry(
            top, textvariable=self.college_search_var,
            placeholder_text="Type college name...",
            fg_color=COLORS["bg_input"], border_color=COLORS["accent_blue"],
            height=36, width=350, font=ctk.CTkFont(size=12)
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            top, text="View Details", height=36,
            fg_color=COLORS["accent_blue"], hover_color=COLORS["highlight"],
            command=self._load_college_detail
        ).pack(side="left", padx=5)

        self.college_detail_label = ctk.CTkLabel(
            tab, text="", font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"]
        )
        self.college_detail_label.pack(anchor="w", padx=15, pady=3)

        self.college_table = self._make_treeview(
            tab,
            columns=["Branch", "FW", "Open Rank", "Close Rank", "Category", "Domicile", "Total", "Round", "Year"],
            widths=[200, 40, 100, 100, 130, 80, 70, 80, 60],
        )

    # ── Actions ──────────────────────────────────────────────────────────────
    def _run_analysis(self):
        rank_str = self.rank_var.get().strip().replace(",", "")
        if not rank_str.isdigit():
            messagebox.showerror("Error", "Please enter a valid JEE rank (numbers only)")
            return

        rank = int(rank_str)
        stats = get_db_stats()
        if stats["total_records"] == 0:
            messagebox.showwarning("No Data", "Please import MPDTE PDFs first via the 'Import PDF' tab.")
            return

        self.analyze_btn.configure(state="disabled", text="⏳ Analyzing...")
        self.predict_status.configure(text="⏳ Analyzing your rank against all colleges...",
                                       text_color=COLORS["accent_yellow"])

        def run():
            try:
                category = self.cat_var.get()
                domicile = self.domicile_var.get()
                fee_waiver = self.fw_var.get()
                branches = self._selected_branches

                summary = generate_summary(rank, category, domicile, fee_waiver, branches)
                self._last_summary = summary
                self._last_results = summary["all_results"]

                self.after(0, lambda: self._display_results(summary))
            except Exception as e:
                logger.error(f"Analysis error: {e}")
                self.after(0, lambda: messagebox.showerror("Error", f"Analysis failed: {e}"))
            finally:
                self.after(0, lambda: self.analyze_btn.configure(
                    state="normal", text="🔍 ANALYZE MY CHANCES"))

        threading.Thread(target=run, daemon=True).start()

    def _display_results(self, summary):
        all_r = summary["all_results"]

        # Update summary labels
        bc = summary.get("band_counts", {})
        self.result_summary_labels["Colleges"].configure(text=str(summary["total_eligible_colleges"]))
        self.result_summary_labels["Extremely Likely"].configure(text=str(bc.get("Extremely Likely", 0)))
        self.result_summary_labels["Likely"].configure(text=str(bc.get("Likely", 0)))
        self.result_summary_labels["Reasonable"].configure(text=str(bc.get("Reasonable", 0)))
        self.result_summary_labels["Borderline"].configure(text=str(bc.get("Borderline", 0)))
        self.result_summary_labels["Stretch"].configure(text=str(bc.get("Stretch", 0)))

        # Fill results table
        self._fill_results_table(all_r)

        # Switch to results tab
        self.tabs.set("📊 Results")

        # Status update
        bc = summary.get("band_counts", {})
        el = bc.get("Extremely Likely", 0)
        li = bc.get("Likely", 0)
        self.predict_status.configure(
            text=(f"✅ Done! {len(all_r)} total options shown. "
                  f"{el} Extremely Likely + {li} Likely options across "
                  f"{summary['total_eligible_colleges']} colleges."),
            text_color=COLORS["accent_green"]
        )

    def _fill_results_table(self, data):
        """Populate results treeview with new band system"""
        tree = self.results_table
        tree.delete(*tree.get_children())

        sort_by = self.sort_var.get()
        if sort_by == "Closing Rank":
            data = sorted(data, key=lambda x: x.get("closing_rank") or 999999)
        elif sort_by == "College Name":
            data = sorted(data, key=lambda x: x.get("institute_name", ""))
        elif sort_by == "Branch":
            data = sorted(data, key=lambda x: x.get("branch_full_name", ""))
        else:
            data = sorted(data, key=lambda x: -x.get("band_score", 0))

        # Band → treeview tag mapping
        band_tags = {
            "Extremely Likely":       "extremely_likely",
            "Likely":                 "likely",
            "Reasonable":             "reasonable",
            "Borderline":             "borderline",
            "Stretch":                "stretch",
            "Historically Unavailable": "historically_unavailable",
        }

        filter_val = self.result_filter_var.get()
        filter_band = None if filter_val == "All" else filter_val

        for rec in data:
            band = rec.get("band", rec.get("risk_level", ""))
            if filter_band and band != filter_band:
                continue

            tag = band_tags.get(band, "")
            fw_sym = "✅" if rec.get("fee_waiver_available") else ""

            tree.insert("", "end", values=(
                rec.get("institute_name", "")[:40],
                rec.get("branch_full_name", "")[:35],
                rec.get("institute_type", "")[:8],
                f"{rec.get('opening_rank', 0):,}" if rec.get("opening_rank") else "-",
                f"{rec.get('closing_rank', 0):,}" if rec.get("closing_rank") else "-",
                rec.get("allotted_category", ""),
                fw_sym,
                band,
                rec.get("explanation", "")[:100],
            ), tags=(tag,))

    def _apply_result_filter(self):
        if self._last_results:
            self._fill_results_table(self._last_results)

    def _generate_strategy(self):
        if not self._last_summary:
            messagebox.showinfo("Info", "Please run analysis first.")
            return

        rank = self._last_summary.get("user_rank", 0)
        category = self.cat_var.get()
        domicile = self.domicile_var.get()
        fee_waiver = self.fw_var.get()

        strategy = generate_counselling_strategy(
            rank, category, domicile, fee_waiver, self._selected_branches
        )

        tree = self.strategy_table
        tree.delete(*tree.get_children())

        self.strategy_label.configure(
            text=f"📋 Optimal Preference Order ({len(strategy)} options) — Higher score = Higher priority",
            text_color=COLORS["accent_green"]
        )

        risk_tags = {
            "Extremely Likely": "extremely_likely",
            "Likely":           "likely",
            "Reasonable":       "reasonable",
            "Borderline":       "borderline",
        }

        for i, rec in enumerate(strategy, 1):
            band = rec.get("band", rec.get("risk_level", ""))
            tag = risk_tags.get(band, "")
            tree.insert("", "end", values=(
                str(i),
                rec.get("institute_name", "")[:38],
                rec.get("branch_full_name", "")[:30],
                rec.get("institute_type", "")[:8],
                f"{rec.get('closing_rank', 0):,}" if rec.get("closing_rank") else "-",
                band,
                f"{rec.get('strategy_score', 0):.1f}",
            ), tags=(tag,))

        self.tabs.set("📋 Strategy")

    def _run_simulator(self):
        rank_str = self.rank_var.get().strip().replace(",", "")
        if not rank_str.isdigit():
            messagebox.showerror("Error", "Enter your rank first.")
            return

        base_rank = int(rank_str)
        sim_ranks = []
        for v in self.sim_vars:
            s = v.get().strip().replace(",", "")
            if s.isdigit():
                sim_ranks.append(int(s))

        category = self.cat_var.get()
        domicile = self.domicile_var.get()
        fee_waiver = self.fw_var.get()

        result = simulate_rank(base_rank, sim_ranks, category, domicile, fee_waiver)

        lines = []
        for rank in sorted(result.keys()):
            r = result[rank]
            total = r["total_useful"]
            el = r.get("Extremely Likely", 0)
            li = r.get("Likely", 0)
            re = r.get("Reasonable", 0)
            bo = r.get("Borderline", 0)
            marker = " ◀ YOUR RANK" if rank == base_rank else ""
            lines.append(
                f"Rank {rank:>8,} → {total:4d} useful options  "
                f"[EL:{el:3d}  Li:{li:3d}  Re:{re:3d}  Bo:{bo:3d}]{marker}"
            )

        self.sim_result_label.configure(
            text="\n".join(lines),
            text_color=COLORS["accent_purple"]
        )

    def _run_range_analysis(self):
        rank_str = self.rank_var.get().strip().replace(",", "")
        if not rank_str.isdigit():
            messagebox.showinfo("Info", "Enter your rank first.")
            return

        rank = int(rank_str)
        margin = int(self.range_margin_var.get())
        category = self.cat_var.get()
        domicile = self.domicile_var.get()
        fee_waiver = self.fw_var.get()

        from core.prediction_engine import analyze_rank_range
        ra = analyze_rank_range(rank, margin, category, domicile, fee_waiver)

        bc_b = ra["best_case"]
        bc_e = ra["expected_case"]
        bc_w = ra["worst_case"]

        lines = [
            f"Margin: ±{margin:,} ranks",
            f"  Best case  (rank {ra['best_rank']:>9,}): {ra['best_useful']:4d} useful options  "
            f"[EL:{bc_b.get('Extremely Likely',0):3d}  Li:{bc_b.get('Likely',0):3d}  "
            f"Re:{bc_b.get('Reasonable',0):3d}  Bo:{bc_b.get('Borderline',0):3d}]",
            f"  Expected   (rank {ra['base_rank']:>9,}): {ra['expected_useful']:4d} useful options  "
            f"[EL:{bc_e.get('Extremely Likely',0):3d}  Li:{bc_e.get('Likely',0):3d}  "
            f"Re:{bc_e.get('Reasonable',0):3d}  Bo:{bc_e.get('Borderline',0):3d}]",
            f"  Worst case (rank {ra['worst_rank']:>9,}): {ra['worst_useful']:4d} useful options  "
            f"[EL:{bc_w.get('Extremely Likely',0):3d}  Li:{bc_w.get('Likely',0):3d}  "
            f"Re:{bc_w.get('Reasonable',0):3d}  Bo:{bc_w.get('Borderline',0):3d}]",
            f"  Sensitivity: {ra['best_useful'] - ra['worst_useful']:+d} options across ±{margin:,} rank margin.",
        ]
        self.range_result_label.configure(
            text="\n".join(lines),
            text_color=COLORS["text_primary"]
        )

    def _show_diagnostics(self):
        if not self._last_results:
            messagebox.showinfo("Info", "Run analysis first.")
            return

        self.diag_text.configure(state="normal")
        self.diag_text.delete("1.0", "end")

        header = (f"  {'College':<36} {'Branch':<12} {'Open':>9} {'Close':>9} "
                  f"{'Δ Open':>9} {'Δ Close':>9}  Band\n")
        self.diag_text.insert("end", header)
        self.diag_text.insert("end", "  " + "─" * 105 + "\n")

        for rec in self._last_results[:15]:
            col  = (rec.get("institute_name") or "")[:35]
            br   = (rec.get("branch_code") or "")[:11]
            op   = rec.get("diag_opening_rank") or 0
            cr   = rec.get("diag_closing_rank") or 0
            d_op = rec.get("diag_dist_from_opening")
            d_cr = rec.get("diag_dist_from_closing")
            band = rec.get("band", "")

            d_op_s = f"{d_op:+,}" if d_op is not None else "N/A"
            d_cr_s = f"{d_cr:+,}" if d_cr is not None else "N/A"

            line = (f"  {col:<36} {br:<12} {op:>9,} {cr:>9,} "
                    f"{d_op_s:>9} {d_cr_s:>9}  {band}\n")
            self.diag_text.insert("end", line)

        self.diag_text.insert("end",
            "\n  Note: Δ Open = user_rank - opening_rank  (negative = user rank is BETTER than opening)\n"
            "        Δ Close = user_rank - closing_rank (negative = user rank is BETTER than closing)\n"
        )
        self.diag_text.configure(state="disabled")

    def _find_missed(self):
        rank_str = self.rank_var.get().strip().replace(",", "")
        if not rank_str.isdigit():
            messagebox.showerror("Error", "Enter your rank first.")
            return

        rank = int(rank_str)
        category = self.cat_var.get()
        domicile = self.domicile_var.get()

        missed = get_missed_opportunities(rank, category, domicile, margin=60000)

        if not missed:
            self.missed_label.configure(
                text="No colleges missed by small margin (within 60,000 ranks).",
                text_color=COLORS["text_secondary"]
            )
            return

        lines = []
        for r in missed[:8]:
            diff = r.get("rank_diff", 0)
            lines.append(
                f"• {r['institute_name'][:35]} | {r.get('branch_full_name', r.get('branch_code', ''))[:25]} "
                f"| Closing: {r['closing_rank']:,} | Miss by: {abs(diff):,} ranks"
            )
        self.missed_label.configure(
            text="\n".join(lines),
            text_color=COLORS["accent_yellow"]
        )

    def _do_search(self):
        query = self.search_var.get().strip()
        filters = {}
        if self.filter_type_var.get() != "All":
            filters["institute_type"] = self.filter_type_var.get()
        if self.filter_fw_var.get():
            filters["fee_waiver"] = True

        results = search_records(query, filters)
        self.search_count_label.configure(text=f"{len(results):,} results")

        tree = self.search_table
        tree.delete(*tree.get_children())

        for i, r in enumerate(results[:1000]):
            tag = "alt" if i % 2 else ""
            tree.insert("", "end", values=(
                r.get("institute_name", "")[:40],
                r.get("branch_full_name", r.get("branch_code", ""))[:35],
                r.get("institute_type", ""),
                "✅" if r.get("fee_waiver_available") else "",
                f"{r.get('opening_rank', 0):,}" if r.get("opening_rank") else "-",
                f"{r.get('closing_rank', 0):,}" if r.get("closing_rank") else "-",
                r.get("allotted_category", ""),
                r.get("domicile", ""),
                r.get("city", ""),
            ), tags=(tag,))

    def _on_result_double_click(self, event):
        tree = self.results_table
        sel = tree.selection()
        if sel:
            vals = tree.item(sel[0])["values"]
            if vals:
                college_name = str(vals[0])
                self.college_search_var.set(college_name)
                self._load_college_detail()
                self.tabs.set("🏫 College Detail")

    def _on_search_double_click(self, event):
        tree = self.search_table
        sel = tree.selection()
        if sel:
            vals = tree.item(sel[0])["values"]
            if vals:
                self.college_search_var.set(str(vals[0]))
                self._load_college_detail()
                self.tabs.set("🏫 College Detail")

    def _load_college_detail(self):
        name = self.college_search_var.get().strip()
        if not name:
            return

        rows = get_college_detail(name)
        if not rows:
            # Try partial match
            results = search_records(name)
            if results:
                rows = get_college_detail(results[0]["institute_name"])
                name = results[0]["institute_name"] if results else name

        self.college_detail_label.configure(
            text=f"🏫 {name} — {len(rows)} records found",
            text_color=COLORS["text_primary"]
        )

        tree = self.college_table
        tree.delete(*tree.get_children())

        for i, r in enumerate(rows):
            tag = "alt" if i % 2 else ""
            tree.insert("", "end", values=(
                r.get("branch_full_name", r.get("branch_code", ""))[:35],
                "✅" if r.get("fee_waiver_available") else "",
                f"{r.get('opening_rank', 0):,}" if r.get("opening_rank") else "-",
                f"{r.get('closing_rank', 0):,}" if r.get("closing_rank") else "-",
                r.get("allotted_category", ""),
                r.get("domicile", ""),
                r.get("total_allotted", ""),
                r.get("round_info", ""),
                r.get("year", ""),
            ), tags=(tag,))

    def _import_pdfs(self):
        files = filedialog.askopenfilenames(
            title="Select MPDTE Counselling PDFs",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
        )
        if not files:
            return

        self.import_progress.set(0)
        self.import_status.configure(text="⏳ Importing...", text_color=COLORS["accent_yellow"])
        self.import_detail.configure(text="")

        def do_import():
            total_imported = 0
            total_dupes = 0
            total_files = len(files)

            for idx, fp in enumerate(files):
                fname = os.path.basename(fp)
                try:
                    self.after(0, lambda f=fname: self.import_status.configure(
                        text=f"Processing: {f}", text_color=COLORS["accent_yellow"]
                    ))
                    self.after(0, lambda p=(idx / total_files): self.import_progress.set(p))

                    records, round_info, year = extract_pdf(fp)
                    imported, dupes = insert_records(records, fname, fp, round_info, year)
                    total_imported += imported
                    total_dupes += dupes

                    self.after(0, lambda i=imported, d=dupes, f=fname: self.import_detail.configure(
                        text=f"✅ {f}: {i:,} imported, {d} duplicates skipped"
                    ))
                except Exception as e:
                    self.after(0, lambda err=e, f=fname: self.import_detail.configure(
                        text=f"❌ {f}: Error - {err}", text_color=COLORS["accent_red"]
                    ))
                    logger.error(f"Import error {fname}: {e}")

            self.after(0, lambda: [
                self.import_progress.set(1.0),
                self.import_status.configure(
                    text=f"✅ Done! {total_imported:,} records imported, {total_dupes} duplicates",
                    text_color=COLORS["accent_green"]
                ),
                self._refresh_stats(),
                self._refresh_pdf_list(),
                self._refresh_branch_list(),
            ])

        threading.Thread(target=do_import, daemon=True).start()

    def _refresh_branch_list(self):
        """Refresh branch checkboxes after import"""
        try:
            tab = self.tabs.tab("🎯 What Can I Get?")
            for w in tab.winfo_children():
                w.destroy()
            self.branch_vars = {}
            self._build_predict_tab()
        except Exception:
            pass

    def _delete_pdf(self, pdf_name: str):
        if messagebox.askyesno("Confirm", f"Delete all records from '{pdf_name}'?"):
            delete_pdf_records(pdf_name)
            self._refresh_pdf_list()
            self._refresh_stats()

    def _quick_filter(self, filter_type: str):
        rank_str = self.rank_var.get().strip().replace(",", "")
        if not rank_str.isdigit():
            messagebox.showerror("Error", "Enter your rank first.")
            return

        rank = int(rank_str)
        category = self.cat_var.get()
        domicile = self.domicile_var.get()
        fee_waiver = self.fw_var.get()

        def run():
            results = get_best_options(rank, category, domicile, fee_waiver, filter_type)
            self._last_results = results
            self.after(0, lambda: [
                self._fill_results_table(results),
                self.tabs.set("📊 Results")
            ])

        threading.Thread(target=run, daemon=True).start()

    def _export_csv(self):
        if not self._last_results:
            messagebox.showinfo("Info", "No results to export. Run analysis first.")
            return
        path = export_csv(self._last_results)
        if path:
            messagebox.showinfo("Exported", f"CSV saved to:\n{path}")

    def _export_excel(self):
        if not self._last_results:
            messagebox.showinfo("Info", "No results to export. Run analysis first.")
            return
        path = export_excel(self._last_results)
        if path:
            messagebox.showinfo("Exported", f"Excel saved to:\n{path}")

    def _export_pdf(self):
        if not self._last_summary:
            messagebox.showinfo("Info", "No analysis results. Run analysis first.")
            return
        path = export_pdf_report(self._last_summary)
        if path:
            messagebox.showinfo("Exported", f"PDF Report saved to:\n{path}")

    def _refresh_stats(self):
        try:
            stats = get_db_stats()
            self.stats_label.configure(
                text=f"📁 {stats['total_pdfs']} PDFs  |  📊 {stats['total_records']:,} Records  |  "
                     f"🏫 {stats['total_colleges']} Colleges  |  📚 {stats['total_branches']} Branches"
            )
        except Exception as e:
            logger.error(f"Stats refresh error: {e}")


def main():
    app = MPDTEApp()
    app.mainloop()


if __name__ == "__main__":
    main()
