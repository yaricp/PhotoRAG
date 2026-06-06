; PhotoRAG NSIS installer customisation
; Included via electron-builder's nsis.include option.
;
; After installation completes, maps the NSIS language selector choice to
; the app's language code and writes bootstrap.json so the backend picks it
; up on first launch — no extra Settings visit required.

!macro customInstall
    ; Map NSIS language ID to PhotoRAG language code.
    ; Default: English. Codes come from NSIS's built-in language IDs.
    StrCpy $0 "en"
    ${If} $LANGUAGE == 1049           ; Russian
        StrCpy $0 "ru"
    ${ElseIf} $LANGUAGE == 3082       ; Spanish (International Sort)
        StrCpy $0 "es"
    ${ElseIf} $LANGUAGE == 1034       ; Spanish (Traditional Sort)
        StrCpy $0 "es"
    ${EndIf}

    ; Write bootstrap.json to %APPDATA%\PhotoRAG\ so the backend reads it
    ; on first launch and sets default_language in the DB automatically.
    CreateDirectory "$APPDATA\PhotoRAG"
    FileOpen $1 "$APPDATA\PhotoRAG\bootstrap.json" w
    FileWrite $1 '{"default_language":"$0"}'
    FileClose $1
!macroend
