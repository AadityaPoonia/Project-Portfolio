import tkinter as tk
from tkinter import messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from Plots.pyplots import *
from pathlib import Path
import os

class Manager(tk.Frame):
    
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller=controller
        self.create_widgets()
    
    def create_widgets(self):
        """
        This function creates all the widgets required for the manager page.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        self.current_report = ""
        self.ReportLabel = tk.Label(self, text="Reports", font=('Arial, 20'))
        self.ReportLabel.place(x=380,y=20,width=103,height=42)

        self.logout_button = tk.Button(self, text="Logout", command=self.controller.logout, borderwidth=0,bg="#F1684B")
        self.logout_button.place(x=770,y=20,width=100,height=30)


        self.report_btn_1 = tk.Button(self, text="Battery Status", command=lambda: self.report_viewer("battery_status"))
        self.report_btn_1.place(x=30,y=80,width=150,height=60)
        self.report_btn_2 = tk.Button(self, text="Vehicle Distribution", command=lambda: self.report_viewer("vehicle_distribution"))
        self.report_btn_2.place(x=30,y=150,width=150,height=60)
        self.report_btn_3 = tk.Button(self, text="Vehicle Types", command=lambda: self.report_viewer("vehicle_types"))
        self.report_btn_3.place(x=30,y=220,width=150,height=60)
        self.report_btn_4 = tk.Button(self, text="Revenue by User", command=lambda: self.report_viewer("revenue_by_user"))
        self.report_btn_4.place(x=30,y=290,width=150,height=60)
        self.report_btn_5 = tk.Button(self, text="Revenue by Date", command=lambda: self.report_viewer("revenue_generated_per_day"))
        self.report_btn_5.place(x=30,y=360,width=150,height=60)
        self.report_btn_5 = tk.Button(self, text="Avg times vehicle used", command=lambda: self.report_viewer("avg_time_of_vehicles_used"))
        self.report_btn_5.place(x=30,y=430,width=150,height=60)
        
        manager_img = tk.PhotoImage(file="images/manager.png")
        self.user_pic = tk.Label(self, image=manager_img, compound="center")
        self.user_pic.image = manager_img
        self.user_pic.place(x=30,y=500,width=150,height=170)

        self.report_frame = tk.Frame(self)
        self.report_frame.place(x=200,y=80,width=670,height=500)

        self.download_report_btn = tk.Button(self, text="Download report  ↓", command=self.download_report, bg="#9fe3bc")
        self.download_report_btn["font"] = ("Arial",20)
    
    def report_viewer(self, report):
        """
        This function displays the report on the screen when the associated report button is clicked.

        Parameters
        ----------
        report : str
            String containing the name of the report to be displayed.(Also used to call the report generating method with the same name)
        
        Returns
        -------
        None
        """
        self.report_frame.destroy()

        self.report_frame = tk.Frame(self)
        self.report_frame.place(x=200,y=80,width=670,height=500)
        self.figure = plt.Figure(figsize=(6,5), dpi=100)
        self.current_report = report

        method_to_call = getattr(Pyplots, report.replace(" ", "_"))
        self.figure = method_to_call(self.figure)
        
        if self.figure == None:
            messagebox.showinfo("Report","This report has no rent data to output")
            return
        
        self.download_report_btn.place(x=385,y=600,width=300,height=50)

        # Adjust margins to fit the chart inside the frame
        self.figure.subplots_adjust(left=0.1, right=0.9, bottom=0.3, top=0.9)

        chart_type = FigureCanvasTkAgg(self.figure, self.report_frame)
        chart_type.get_tk_widget().pack(fill="both", expand=False)

        # popup_window.bind("<FocusOut>", popup_window.destroy)

    def download_report(self):
        """
        This function downloads the currently displayed report to the Downloads folder or a local folder in the project report if the downloads folder doesnt exist.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        if self.current_report != "":
            download_path = f"{Path.home()}\\Downloads"
            if os.path.exists(download_path):
                self.figure.savefig(f"{download_path}\\{self.current_report}.png")
            else:
                self.figure.savefig(f"downloaded_reports/{self.current_report}.png")
                
            messagebox.showinfo("Download","Report downloaded successfully!")