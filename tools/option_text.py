"""Text for the patch's two Options rows, by the game's message folder index (the word at 0x1614B34).
Each entry: Enable Wild Battle title, its description, Level-Up Trade Evolution title, its description.
Written by Claude, using the game's own terms and Pokémon names. Corrections from native speakers are welcome."""

FOLDERS = {
    0: "JPN",
    1: "JPN_KANJI",
    2: "English",
    3: "French",
    4: "Italian",
    5: "German",
    6: "Spanish",
    7: "Korean",
    8: "Simp_Chinese",
    9: "Trad_Chinese",
}

TEXT = {
    0: (
        "やせいポケモンと　バトル",
        "やせいの　ポケモンと　バトルできます\nオフで　もとの　つかまえかたに　もどります",
        "こうかんなしで　しんか",
        "ユンゲラー　ゴーリキー　ゴローン　ゴーストが\nレベル50から　こうかんなしで　しんかします",
    ),
    1: (
        "野生ポケモンと　バトル",
        "野生の　ポケモンと　バトルできます\nオフで　元の　つかまえかたに　戻ります",
        "交換なしで　進化",
        "ユンゲラー　ゴーリキー　ゴローン　ゴーストが\nレベル50から　交換なしで　進化します",
    ),
    2: (
        "Enable Wild Battle",
        "Battle wild Pokémon before catching them.\nTurn this off for the game’s normal catching.",
        "Level-Up Trade Evolution",
        "Kadabra, Machoke, Graveler and Haunter can also\nevolve by leveling up, starting at Level 50.",
    ),
    3: (
        "Combats sauvages",
        "Combattez les Pokémon sauvages avant de les\ncapturer. Désactivez pour la capture normale.",
        "Évolution sans échange",
        "Kadabra, Machopeur, Gravalanch et Spectrum\npeuvent aussi évoluer dès le N. 50 sans échange.",
    ),
    4: (
        "Lotta con i selvatici",
        "Lotta contro i Pokémon selvatici prima di\ncatturarli. Scegli No per la cattura normale.",
        "Evoluzione senza scambio",
        "Kadabra, Machoke, Graveler e Haunter possono\nevolversi anche senza scambio dal Livello 50.",
    ),
    5: (
        "Wilde Pokémon bekämpfen",
        "Kämpfe gegen wilde Pokémon, bevor du sie fängst.\nWähle „Aus“ für das normale Fangen.",
        "Entwicklung ohne Tausch",
        "Kadabra, Maschock, Georok und Alpollo können\nsich ab Level 50 auch ohne Tausch entwickeln.",
    ),
    6: (
        "Combates salvajes",
        "Combate contra Pokémon salvajes antes de\ncapturarlos. Elige No para capturar como siempre.",
        "Evolución sin intercambio",
        "Kadabra, Machoke, Graveler y Haunter también\nevolucionan sin intercambio desde el nivel 50.",
    ),
    7: (
        "야생 포켓몬 배틀",
        "잡기 전에 야생 포켓몬과 배틀합니다\nOff로 하면 원래 방식으로 잡습니다",
        "교환 없이 진화",
        "윤겔라, 근육몬, 데구리, 고우스트가\n레벨 50부터 교환 없이 진화합니다",
    ),
    8: (
        "野生宝可梦对战",
        "捕捉前可以与野生宝可梦对战。\n关闭后恢复原来的捕捉方式。",
        "无需交换进化",
        "勇基拉、豪力、隆隆石、鬼斯通\n从等级50起无需交换也能进化。",
    ),
    9: (
        "野生寶可夢對戰",
        "捕捉前可以與野生寶可夢對戰。\n關閉後恢復原本的捕捉方式。",
        "無需交換進化",
        "勇基拉、豪力、隆隆石、鬼斯通\n從等級50起無需交換也能進化。",
    ),
}
