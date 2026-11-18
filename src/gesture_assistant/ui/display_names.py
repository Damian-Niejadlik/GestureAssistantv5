"""Polish presentation labels; these never replace persisted identifiers."""

GROUPS = {
    "teams": ("Teams", {
        "toggle_mute": "Włącz lub wycisz mikrofon", "toggle_raise_hand": "Podnieś lub opuść rękę",
        "toggle_camera": "Włącz lub wyłącz kamerę", "reaction_like": "Wyślij reakcję Lubię to",
        "reaction_applause": "Wyślij reakcję Brawa", "leave_meeting": "Opuść spotkanie",
    }),
    "browser": ("Przeglądarka", {
        "open_url": "Otwórz stronę internetową", "new_tab": "Otwórz nową kartę",
        "close_tab": "Zamknij kartę", "next_tab": "Przejdź do następnej karty",
        "previous_tab": "Przejdź do poprzedniej karty", "refresh_page": "Odśwież stronę",
        "go_back": "Wróć do poprzedniej strony",
    }),
    "system": ("Windows", {
        "toggle_mute": "Wycisz lub przywróć dźwięk", "take_screenshot": "Zrób zrzut ekranu",
        "lock": "Zablokuj ekran", "close_active_window": "Zamknij aktywne okno",
        "switch_virtual_desktop": "Przełącz pulpit wirtualny",
        "launch_application": "Uruchom aplikację",
    }),
    "media": ("Multimedia", {
        "play_pause": "Odtwórz lub wstrzymaj", "stop": "Zatrzymaj odtwarzanie",
        "volume_up": "Zwiększ głośność", "volume_down": "Zmniejsz głośność",
        "next_track": "Przejdź do następnego utworu",
        "previous_track": "Przejdź do poprzedniego utworu",
    }),
    "presentation": ("Prezentacja", {
        "next_slide": "Przejdź do następnego slajdu",
        "previous_slide": "Wróć do poprzedniego slajdu",
        "start_presentation": "Rozpocznij pokaz slajdów",
        "end_presentation": "Zakończ pokaz slajdów",
    }),
}

GESTURES = {
    "TRIANGLE": ("Trójkąt", "Połącz opuszki palców wskazujących u góry, kciuków na dole."),
    "DOUBLE_FIST": ("Dwie pięści", "Zaciśnij obie pięści i pokaż je obok siebie."),
    "DOUBLE_THUMBS_UP": ("Dwa kciuki w górę", "Pokaż jednocześnie oba kciuki skierowane w górę."),
    "OPEN_PALM": ("Otwarta dłoń", "Rozprostuj palce i skieruj dłoń do kamery."),
    "FIST": ("Pięść", "Zegnij wszystkie palce, formując pięść."),
    "VICTORY": ("Znak V", "Wyprostuj palec wskazujący i środkowy, pozostałe zegnij."),
    "THUMBS_UP": ("Kciuk w górę", "Zegnij palce i skieruj wyprostowany kciuk w górę."),
    "THUMBS_DOWN": ("Kciuk w dół", "Zegnij palce i skieruj wyprostowany kciuk w dół."),
    "POINTING_UP": ("Wskazanie w górę", "Wyprostuj tylko palec wskazujący."),
    "PINCH": ("Złączenie palców", "Zbliż opuszki kciuka i palca wskazującego."),
    "ROCK": ("Gest rock", "Wyprostuj kciuk i mały palec. Zegnij trzy pozostałe."),
    "SWIPE_LEFT": ("Ruch w lewo", "Przesuń otwartą dłoń w lewo na podglądzie."),
    "SWIPE_RIGHT": ("Ruch w prawo", "Przesuń otwartą dłoń w prawo na podglądzie."),
    "SWIPE_UP": ("Ruch w górę", "Przesuń otwartą dłoń w górę na podglądzie."),
    "SWIPE_DOWN": ("Ruch w dół", "Przesuń otwartą dłoń w dół na podglądzie."),
}

PROFILES = {"Auto": "Automatyczny", "Browser": "Przeglądarka", "Teams": "Teams",
            "Media": "Multimedia", "Presentation": "Prezentacja", "System": "Windows",
            "Unknown": "Nieustalony"}


def action_name(identifier, grouped=False):
    if identifier == "sleep_computer":
        return "Windows · Uśpij komputer" if grouped else "Uśpij komputer"
    if not identifier or identifier == "none":
        return "Brak przypisanej akcji"
    category, _, name = identifier.partition(".")
    group, names = GROUPS.get(category, ("", {}))
    title = names.get(name, "Nierozpoznana akcja")
    return f"{group} · {title}" if grouped and group else title


def gesture_name(identifier):
    return GESTURES.get(identifier, ("—", ""))[0]

