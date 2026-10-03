import tkinter as tk
from tkinter import messagebox

class Calculator:
    def __init__(self, root):
        self.root = root
        self.root.title("Калькулятор")
        self.root.geometry("320x450")
        self.root.resizable(False, False)
        self.root.configure(bg="#1e1e1e")

      
        self.expression = ""
        self.entry_text = tk.StringVar()

      
        self.display = tk.Entry(
            root,
            textvariable=self.entry_text,
            font=("Arial", 24),
            bg="#2b2b2b",
            fg="white",
            bd=0,
            justify="right",
            insertbackground="white"
        )
        self.display.grid(row=0, column=0, columnspan=4, padx=10, pady=20, ipady=15, sticky="nsew")

       
        buttons = [
            ("C", 1, 0, "#d9534f"), ("⌫", 1, 1, "#f0ad4e"), ("%", 1, 2, "#5bc0de"), ("/", 1, 3, "#5bc0de"),
            ("7", 2, 0, "#3c3c3c"), ("8", 2, 1, "#3c3c3c"), ("9", 2, 2, "#3c3c3c"), ("*", 2, 3, "#5bc0de"),
            ("4", 3, 0, "#3c3c3c"), ("5", 3, 1, "#3c3c3c"), ("6", 3, 2, "#3c3c3c"), ("-", 3, 3, "#5bc0de"),
            ("1", 4, 0, "#3c3c3c"), ("2", 4, 1, "#3c3c3c"), ("3", 4, 2, "#3c3c3c"), ("+", 4, 3, "#5bc0de"),
            ("0", 5, 0, "#3c3c3c"), (".", 5, 1, "#3c3c3c"), ("=", 5, 2, "#5cb85c", 2),
        ]

    
        for i in range(6):
            root.grid_rowconfigure(i, weight=1)
        for i in range(4):
            root.grid_columnconfigure(i, weight=1)


        for btn in buttons:
            text, row, col, color = btn[0], btn[1], btn[2], btn[3]
            colspan = btn[4] if len(btn) > 4 else 1
            tk.Button(
                root, text=text, font=("Arial", 18, "bold"),
                bg=color, fg="white", bd=0, activebackground="#666",
                command=lambda t=text: self.on_click(t)
            ).grid(row=row, column=col, columnspan=colspan, padx=5, pady=5, sticky="nsew")

        root.bind("<Return>", lambda e: self.on_click("="))
        root.bind("<BackSpace>", lambda e: self.on_click("⌫"))
        root.bind("<Key>", self.key_press)

    def key_press(self, event):
        if event.char in "0123456789+-*/.%":
            self.on_click(event.char)
        elif event.char == "=":
            self.on_click("=")

    def on_click(self, value):
        if value == "C":
            self.expression = ""
        elif value == "⌫":
            self.expression = self.expression[:-1]
        elif value == "=":
            try:
        
                expr = self.expression.replace("%", "/100")
                result = eval(expr, {"__builtins__": None}, {})
                self.expression = str(result)
            except ZeroDivisionError:
                messagebox.showerror("Ошибка", "Деление на ноль!")
                self.expression = ""
            except Exception:
                messagebox.showerror("Ошибка", "Некорректное выражение")
                self.expression = ""
        else:
            self.expression += value

        self.entry_text.set(self.expression)


if __name__ == "__main__":
    root = tk.Tk()
    app = Calculator(root)
    root.mainloop()
