import sys, time
sys.path.insert(0, r"D:\Projects\deepseek-pet\src")
import tkinter as tk
import customtkinter as ctk
from PIL import ImageGrab
ctk.set_appearance_mode("light")
r=ctk.CTk(); r.geometry("420x330+300+300"); r.configure(fg_color="#EDEEF2")
G="#34C759"; F="#D7D8DE"; W="#FFFFFF"
variants=[
 ("1 defaults text=''", dict(text="", progress_color=G, fg_color=F, switch_width=40, switch_height=22)),
 ("2 +btn white", dict(text="", progress_color=G, fg_color=F, switch_width=40, switch_height=22, button_color=W)),
 ("3 +corner12 bl20", dict(text="", progress_color=G, fg_color=F, switch_width=44, switch_height=24, corner_radius=12, button_length=20, button_color=W)),
 ("4 +border0", dict(text="", progress_color=G, fg_color=F, switch_width=44, switch_height=24, corner_radius=12, button_length=20, button_color=W, border_width=0)),
]
for i,(name,kw) in enumerate(variants):
    v=tk.BooleanVar(value=bool(i%2==0))
    ctk.CTkLabel(r,text=name,font=ctk.CTkFont(family="Microsoft YaHei UI",size=11),text_color="#333").pack(anchor="w",padx=20,pady=(6,0))
    ctk.CTkSwitch(r,variable=v,**kw).pack(anchor="w",padx=20)
r.update(); time.sleep(0.4); r.update()
x,y=r.winfo_x(),r.winfo_y(); w,h=r.winfo_width(),r.winfo_height()
ImageGrab.grab(bbox=(x,y,x+w,y+h)).save(r"C:\Users\admin\.openclaw-desktop\.openclaw\workspace\_sw.png")
r.destroy(); print("ok")
