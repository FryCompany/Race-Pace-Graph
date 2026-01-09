import sys
import json
import pandas as pd
import plotly.express as px
from urllib.request import urlopen
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLineEdit, QLabel, QMessageBox, QComboBox)
from PyQt6.QtWebEngineWidgets import QWebEngineView
import colorsys

class F1Dashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("F1 Race Pace Analyzer - Session Finder")
        self.setGeometry(100, 100, 1300, 850)
        
        self.team_colors = {
            "Red Bull Racing": "#3671C6", "Ferrari": "#E80020", "Mercedes": "#27F4D2",
            "McLaren": "#FF8000", "Aston Martin": "#229971", "Alpine": "#0093CC",
            "Williams": "#64C4FF", "RB": "#6692FF", "Sauber": "#52E252", "Haas F1 Team": "#B6BABD",
            "AlphaTauri": "#2B4562", "Alfa Romeo": "#900000", "Kick Sauber": "#52E252"
        }
        self.driver_to_team = {} 
        self.driver_to_name = {}

        self.init_ui()
        self.update_meetings() 

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

       
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("Year:"))
        self.combo_year = QComboBox()
        self.combo_year.addItems(["2025", "2024", "2023"])
        self.combo_year.currentTextChanged.connect(self.update_meetings)
        filter_layout.addWidget(self.combo_year)

        filter_layout.addWidget(QLabel("Grand Prix (Race):"))
        self.combo_race = QComboBox()
        self.combo_race.setMinimumWidth(300)
        filter_layout.addWidget(self.combo_race)

        filter_layout.addWidget(QLabel("Driver Numbers"))
        self.driver_input = QLineEdit()
        self.driver_input.setPlaceholderText("Es: 16 55 1")
        filter_layout.addWidget(self.driver_input)

        self.btn_load = QPushButton("Load Race Data")
        self.btn_load.clicked.connect(self.load_race_data)
        filter_layout.addWidget(self.btn_load)
        
        layout.addLayout(filter_layout)

        self.browser = QWebEngineView()
        layout.addWidget(self.browser)

    def update_meetings(self):
       
        year = self.combo_year.currentText()
       
        url = f"https://api.openf1.org/v1/sessions?year={year}&session_name=Race"
        
        try:
            self.combo_race.clear()
            response = urlopen(url)
            sessions = json.loads(response.read().decode("utf-8"))
            
           
            sessions.sort(key=lambda x: x['date_start'])
            
            for s in sessions:
                
                display_name = s.get('circuit_short_name', 'Unknown GP')
                session_key = s['session_key']
                
                
                self.combo_race.addItem(display_name, session_key)
                
        except Exception as e:
            print(f"Errore caricamento sessioni: {e}")

    def fetch_driver_info(self, session_key):
        """Associa numeri piloti a nomi e team per la sessione specifica"""
        url = f"https://api.openf1.org/v1/drivers?session_key={session_key}"
        try:
            response = urlopen(url)
            drivers = json.loads(response.read().decode("utf-8"))
           
            self.driver_to_team = {str(d['driver_number']): d['team_name'] for d in drivers}
            self.driver_to_name = {str(d['driver_number']): d['last_name'].upper() for d in drivers}
        except Exception as e:
            print(f"Errore driver info: {e}")

    def adjust_color(self, hex_color, factor=1.4):
        if not hex_color: return "#000000"
        hex_color = hex_color.lstrip('#')
        try:
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            hls = colorsys.rgb_to_hls(rgb[0]/255.0, rgb[1]/255.0, rgb[2]/255.0)
            new_l = max(0, min(1, hls[1] * factor if hls[1] < 0.5 else hls[1] / factor))
            new_rgb = colorsys.hls_to_rgb(hls[0], new_l, hls[2])
            return '#%02x%02x%02x' % (int(new_rgb[0]*255), int(new_rgb[1]*255), int(new_rgb[2]*255))
        except:
            return "#000000"

    def load_race_data(self):
      
        session_key = self.combo_race.currentData()
        
        if not session_key:
            QMessageBox.warning(self, "Warning","Please select a Grand Prix from the list (make sure it has been loaded).")
            return

        
        raw_text = self.driver_input.text()
        nums = [p.strip() for p in raw_text.replace(',', ' ').split() if p.strip()]
        if not nums:
            QMessageBox.warning(self, "Input", "Please enter the drivers' numbers.")
            return

        
        self.fetch_driver_info(session_key)
        
        
        base_url = f"https://api.openf1.org/v1/laps?lap_number>1&session_key={session_key}&is_pit_out_lap=false"
        filter_drivers = "".join([f"&driver_number={n}" for n in nums])
        
        try:
            full_url = base_url + filter_drivers
           
            
            response = urlopen(full_url)
            data = json.loads(response.read().decode("utf-8"))
            df = pd.DataFrame(data)
            
            if df.empty:
                QMessageBox.information(self, "Data", "No data found for the selected drivers in this session.")
                return

            df["driver_number"] = df["driver_number"].astype(str)
            df["label"] = df["driver_number"].apply(lambda x: f"{x} {self.driver_to_name.get(x, 'N/A')}")
            
            
            def format_lap(s): 
                if pd.isna(s): return ""
                return f"{int(s//60)}:{s%60:06.3f}"
            
            df["lap_duration_fmt"] = df["lap_duration"].apply(format_lap)

            
            color_map = {}
            team_count = {}
            
           
            unique_drivers = df["driver_number"].unique()
            
            for n in unique_drivers:
                team = self.driver_to_team.get(n, "Unknown")
                base_color = self.team_colors.get(team, "#333333")
                lbl = f"{n} {self.driver_to_name.get(n, 'N/A')}"
                
                if team not in team_count:
                    color_map[lbl] = base_color
                    team_count[team] = 1
                else:
                    color_map[lbl] = self.adjust_color(base_color)

            
            fig = px.line(
                df, x="lap_number", y="lap_duration", color="label",
                title=f"Analisi Passo Gara: {self.combo_race.currentText()}",
                markers=True, color_discrete_map=color_map,
                hover_data={"lap_duration": False, "lap_duration_fmt": True, "label": True}
            )
            fig.update_layout(
                template="plotly_dark", 
                yaxis_title="Tempo Giro (s)", 
                xaxis_title="Giro",
                hovermode="x unified" 
            )
            


            self.display_plotly(fig)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred:\n{str(e)}")

    def display_plotly(self, fig):
        html = fig.to_html(include_plotlyjs='cdn')
        self.browser.setHtml(html)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = F1Dashboard()
    window.show()
    sys.exit(app.exec())