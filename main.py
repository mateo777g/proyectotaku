import flet as ft
from controllers.main_controller import MainController

def main(page: ft.Page):
    MainController(page)

if __name__ == "__main__":
    ft.run(main, assets_dir=".")