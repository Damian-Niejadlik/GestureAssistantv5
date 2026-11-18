# GestureAssistant

GestureAssistant używa kamery do rozpoznawania gestów dłoni i sterowania aplikacjami na Windows. Możesz sprawdzić gesty bez wykonywania poleceń, przypisać własne akcje i dopasować rozpoznawanie lokalną kalibracją. Nie potrzebujesz konta ani uprawnień administratora.

## Wymagania

- Windows, kamera internetowa i Python 3.12 (zalecany punkt wyjścia).
- Dostęp do internetu przy instalacji zależności i jawnym pobraniu modelu dłoni. Późniejsza analiza obrazu odbywa się lokalnie.
- Zależności są definiowane w `pyproject.toml`, w tym PySide6, MediaPipe, OpenCV i PyGetWindow na Windows.

## Pobranie i instalacja

Jeżeli masz archiwum źródeł, rozpakuj je do nowego folderu i otwórz PowerShell w katalogu zawierającym `main.py`. Alternatywnie pobierz repozytorium:

```powershell
git clone https://github.com/Damian-Niejadlik/GestureAssistant.git
Set-Location GestureAssistant
```

Pobranie z GitHuba nie gwarantuje, że zdalna gałąź zawiera zmiany z nowszego archiwum. Nie mieszaj plików z różnych kopii.

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e .
& .\.venv\Scripts\python.exe .\scripts\download_model.py
& .\.venv\Scripts\python.exe .\main.py
```

Polecenie pobierania zapisuje model w `models/hand_landmarker.task`. Aplikacja nie pobiera go przy starcie. Bez modelu lub kamery podgląd nie może działać. Jeżeli masz już działający model w poprzedniej kopii, możesz przenieść sam plik modelu zamiast pobierać go drugi raz.

## Pierwsze uruchomienie

1. Na karcie **Start** wybierz profil. **Automatyczny** dobiera profil na podstawie aktywnego okna. Wybór profilu nie uruchamia kamery ani akcji.
2. W **Podgląd i sterowanie** uruchom kamerę. Ustaw równomierne światło i zmieść całą dłoń w kadrze. **Lustro** i **Obrót 180°** zmieniają orientację obrazu oraz punktów dłoni. Po zmianie orientacji sprawdź stan sterowania.
3. Na początek użyj **Demo** albo **Symulacji**. Demo pokazuje rozpoznawanie z kamery bez wykonawcy akcji. Symulacja pokazuje wyniki dla dopuszczonych akcji, ale ich nie wysyła.
4. Jeżeli chcesz sterować komputerem, włącz wykonywanie w ustawieniach, wyłącz symulację i użyj przycisku **Włącz sterowanie gestami**. Przy akcjach kierowanych do programu ustaw fokus na jego oknie.

Możesz uruchomić demo lub użyć przykładowej konfiguracji bez nadpisywania własnej:

```powershell
& .\.venv\Scripts\python.exe .\main.py --demo
& .\.venv\Scripts\python.exe .\main.py --config .\examples\actions_dry_run.json
```

Przykład jest przeznaczony do symulacji. Jeżeli chcesz zachować go jako wzorzec, uruchom aplikację na kopii pliku: GUI może zapisywać zmiany do konfiguracji podanej przez `--config`.

## Ustawienia

| Zakładka | Zastosowanie |
|---|---|
| Profile akcji | Wybór przypisań globalnych lub dla profilu. Ustaw adres lub skrót, jeśli akcja tego wymaga, zaznacz jej zezwolenie i zapisz. Globalne „brak akcji” blokuje również mapowanie profilu; „dziedzicz” go nie nadpisuje. |
| Gesty i ruchy | Czułość, czas przytrzymania, parametry ruchu i przerwy pomiędzy akcjami. Zaczynaj od ustawień domyślnych. |
| Kamera | Numer urządzenia, docelowe FPS i rozdzielczość. Urządzenie może nie obsłużyć wybranej kombinacji. Zmiany parametrów zastosuj od następnej sesji. |
| Potwierdzenie akcji i bezpieczeństwo | Wykonywanie akcji, symulacja oraz osobne zezwolenia na akcje wrażliwe. Uśpienie ma dodatkowy przełącznik. |
| Wygląd | Motyw jasny lub ciemny, dwa niezależne akcenty dla każdego motywu, przywrócenie palety domyślnej. Zmiana jest natychmiastowa i zapisywana lokalnie. Kolor o zbyt niskim kontraście jest odrzucany. |

### Gesty i akcje

- Jedna dłoń: otwarta dłoń, pięść, kciuk w górę i w dół, znak V, wskazanie w górę, złączenie palców oraz gest „rock” (wyprostowany kciuk i mały palec).
- Ruchy: lewo, prawo, góra i dół w układzie podglądu. Dwie niejednoznaczne komendy mogą zostać odrzucone.
- Dwie dłonie: trójkąt, dwie pięści i dwa kciuki w górę. Dwa kciuki są zarezerwowane do potwierdzania; nie używaj ich jako zwykłego przypisania.
- Dostępne profile obejmują Teams, przeglądarkę, PowerPoint, multimedia i czynności Windows. Skróty zależą od programu; m.in. reakcje Teams wymagają skonfigurowanego skrótu. Globalny klawisz multimedialny może trafić do innej sesji odtwarzania.

Rozpoznany gest nie jest równoznaczny z wykonaniem. W podglądzie sprawdź przypisanie, aktywne okno, stabilizację i ostatni wynik. Otwarcie URL wymaga skonfigurowanego adresu HTTPS. Wysłanie skrótu nie dowodzi, że docelowy program wykonał polecenie.

### Akcje wymagające potwierdzenia

1. Dopuść konkretną akcję w zakładce bezpieczeństwa i osobno w profilu akcji.
2. Przy aktywnym oknie docelowym pokaż przypisany gest. Poczekaj na instrukcję na pasku stanu lub powiadomienie systemowe.
3. Nie przełączaj okna. Przytrzymaj dwa kciuki w górę przez co najmniej dwie sekundy. Prośba wygasa po 15 sekundach. Wyłączenie sterowania lub zmiana okna przerywa oczekujące potwierdzenie.

Zamknięcie okna wysyła `Alt+F4`; okno może np. zapytać o zapis, a aplikacja nie weryfikuje skutku skrótu. Nie testuj tego na dokumentach zawierających niezapisane dane.

### Kalibracja

Na karcie **Kalibracja gestów** uruchom kamerę do kalibracji i wybierz pozycję jednej dłoni. Zapisz 10 oddzielnych próbek w co najmniej trzech obszarach obrazu, zdejmując dłoń z kadru między zapisami. Włącz używanie kalibracji i rozpocznij nową sesję. Próbki są przypisane do numeru kamery i orientacji. Kalibracja uzupełnia nierozpoznane pozycje pojedynczej dłoni; nie trenuje MediaPipe i nie obsługuje ruchów ani par dłoni.

## Dane i prywatność

- Projekt źródłowy zapisuje `config.json` obok `main.py`, chyba że jawnie podano inny plik. Przed zmianą wydania wykonaj kopię prywatnej konfiguracji. Nie publikuj jej z projektem.
- Wygląd, orientacja i próbki kalibracji są zapisywane jako lokalne ustawienia użytkownika Qt. Próbki zawierają znormalizowane cechy dłoni, nie zdjęcia ani nagrania.
- Historia obejmuje wyniki bieżącego procesu, nie jest zachowywana między restartami. W **Historii** możesz ją filtrować, usunąć lub wyeksportować do CSV.
- Nie ma automatycznego nagrywania. Jawnie przypisana akcja zrzutu ekranu zapisuje pulpit lokalnie w `GestureAssistant/Screenshots` w katalogu domowym. Otwieranie strony uruchamia przeglądarkę.

## Rozwiązywanie problemów

| Objaw | Co sprawdzić |
|---|---|
| Brak modelu | Uruchom `scripts/download_model.py`, sprawdź plik w `models/`. |
| Brak obrazu | Sprawdź uprawnienia Windows do kamery i zamknij inne aplikacje korzystające z niej. Sprawdź numer urządzenia. |
| Gest jest widoczny, ale nic nie robi | Sprawdź symulację, stan sterowania, uprawnienia w profilu, stabilizację i fokus celu. |
| Nieznany kontekst dla każdego programu | Sprawdź `python -m pip show PyGetWindow` używając tego samego Pythona z `.venv`. |
| Brak powiadomień | Sprawdź zasobnik i ustawienia powiadomień Windows. Instrukcja pojawia się też na pasku stanu. |
| Brak opcji `py` | Użyj `python` z PATH po potwierdzeniu wersji poleceniem `python --version`. |

## Rozwój i weryfikacja

```powershell
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
& .\.venv\Scripts\python.exe -m pytest -v
& .\.venv\Scripts\python.exe -m ruff check .
```

Rozpoznawanie korzysta z heurystyk i może mylić gesty przy zasłonięciu dłoni lub słabym świetle. Testy syntetyczne nie są pomiarem skuteczności rozpoznawania. Przed prezentacją sprawdź start, obie palety, kamerę, zakończenie sesji i powiadomienia na docelowym Windows. Projekt nie jest narzędziem medycznym.
