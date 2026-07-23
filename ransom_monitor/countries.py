"""Nombres en español para códigos ISO 3166-1 alpha-2.

Se usa en el feed global (que trae víctimas de cualquier país del mundo, no
solo LATAM) para mostrar el nombre del país de cada víctima en su tarjeta.
Los feeds de país ya tienen su nombre en `config/countries/<código>.yaml` y
no dependen de esta tabla.
"""

from __future__ import annotations

_NAMES_ES = {
    "AD": "Andorra", "AE": "Emiratos Árabes Unidos", "AF": "Afganistán",
    "AG": "Antigua y Barbuda", "AI": "Anguila", "AL": "Albania", "AM": "Armenia",
    "AO": "Angola", "AR": "Argentina", "AS": "Samoa Americana", "AT": "Austria",
    "AU": "Australia", "AW": "Aruba", "AZ": "Azerbaiyán", "BA": "Bosnia y Herzegovina",
    "BB": "Barbados", "BD": "Bangladés", "BE": "Bélgica", "BF": "Burkina Faso",
    "BG": "Bulgaria", "BH": "Baréin", "BI": "Burundi", "BJ": "Benín",
    "BM": "Bermudas", "BN": "Brunéi", "BO": "Bolivia", "BR": "Brasil",
    "BS": "Bahamas", "BT": "Bután", "BW": "Botsuana", "BY": "Bielorrusia",
    "BZ": "Belice", "CA": "Canadá", "CD": "República Democrática del Congo",
    "CF": "República Centroafricana", "CG": "República del Congo", "CH": "Suiza",
    "CI": "Costa de Marfil", "CK": "Islas Cook", "CL": "Chile", "CM": "Camerún",
    "CN": "China", "CO": "Colombia", "CR": "Costa Rica", "CU": "Cuba",
    "CV": "Cabo Verde", "CW": "Curazao", "CY": "Chipre", "CZ": "Chequia",
    "DE": "Alemania", "DJ": "Yibuti", "DK": "Dinamarca", "DM": "Dominica",
    "DO": "República Dominicana", "DZ": "Argelia", "EC": "Ecuador", "EE": "Estonia",
    "EG": "Egipto", "EH": "Sahara Occidental", "ER": "Eritrea", "ES": "España",
    "ET": "Etiopía", "FI": "Finlandia", "FJ": "Fiyi", "FM": "Micronesia",
    "FO": "Islas Feroe", "FR": "Francia", "GA": "Gabón", "GB": "Reino Unido",
    "GD": "Granada", "GE": "Georgia", "GF": "Guayana Francesa", "GG": "Guernsey",
    "GH": "Ghana", "GI": "Gibraltar", "GL": "Groenlandia", "GM": "Gambia",
    "GN": "Guinea", "GP": "Guadalupe", "GQ": "Guinea Ecuatorial", "GR": "Grecia",
    "GT": "Guatemala", "GU": "Guam", "GW": "Guinea-Bisáu", "GY": "Guyana",
    "HK": "Hong Kong", "HN": "Honduras", "HR": "Croacia", "HT": "Haití",
    "HU": "Hungría", "ID": "Indonesia", "IE": "Irlanda", "IL": "Israel",
    "IM": "Isla de Man", "IN": "India", "IQ": "Irak", "IR": "Irán",
    "IS": "Islandia", "IT": "Italia", "JE": "Jersey", "JM": "Jamaica",
    "JO": "Jordania", "JP": "Japón", "KE": "Kenia", "KG": "Kirguistán",
    "KH": "Camboya", "KI": "Kiribati", "KM": "Comoras", "KN": "San Cristóbal y Nieves",
    "KP": "Corea del Norte", "KR": "Corea del Sur", "KW": "Kuwait",
    "KY": "Islas Caimán", "KZ": "Kazajistán", "LA": "Laos", "LB": "Líbano",
    "LC": "Santa Lucía", "LI": "Liechtenstein", "LK": "Sri Lanka", "LR": "Liberia",
    "LS": "Lesoto", "LT": "Lituania", "LU": "Luxemburgo", "LV": "Letonia",
    "LY": "Libia", "MA": "Marruecos", "MC": "Mónaco", "MD": "Moldavia",
    "ME": "Montenegro", "MF": "San Martín", "MG": "Madagascar",
    "MH": "Islas Marshall", "MK": "Macedonia del Norte", "ML": "Malí",
    "MM": "Birmania", "MN": "Mongolia", "MO": "Macao", "MP": "Islas Marianas del Norte",
    "MQ": "Martinica", "MR": "Mauritania", "MS": "Montserrat", "MT": "Malta",
    "MU": "Mauricio", "MV": "Maldivas", "MW": "Malaui", "MX": "México",
    "MY": "Malasia", "MZ": "Mozambique", "NA": "Namibia", "NC": "Nueva Caledonia",
    "NE": "Níger", "NG": "Nigeria", "NI": "Nicaragua", "NL": "Países Bajos",
    "NO": "Noruega", "NP": "Nepal", "NR": "Nauru", "NU": "Niue",
    "NZ": "Nueva Zelanda", "OM": "Omán", "PA": "Panamá", "PE": "Perú",
    "PF": "Polinesia Francesa", "PG": "Papúa Nueva Guinea", "PH": "Filipinas",
    "PK": "Pakistán", "PL": "Polonia", "PM": "San Pedro y Miquelón",
    "PR": "Puerto Rico", "PS": "Palestina", "PT": "Portugal", "PW": "Palaos",
    "PY": "Paraguay", "QA": "Catar", "RE": "Reunión", "RO": "Rumania",
    "RS": "Serbia", "RU": "Rusia", "RW": "Ruanda", "SA": "Arabia Saudita",
    "SB": "Islas Salomón", "SC": "Seychelles", "SD": "Sudán", "SE": "Suecia",
    "SG": "Singapur", "SH": "Santa Elena", "SI": "Eslovenia", "SK": "Eslovaquia",
    "SL": "Sierra Leona", "SM": "San Marino", "SN": "Senegal", "SO": "Somalia",
    "SR": "Surinam", "SS": "Sudán del Sur", "ST": "Santo Tomé y Príncipe",
    "SV": "El Salvador", "SX": "Sint Maarten", "SY": "Siria", "SZ": "Esuatini",
    "TC": "Islas Turcas y Caicos", "TD": "Chad", "TG": "Togo", "TH": "Tailandia",
    "TJ": "Tayikistán", "TL": "Timor Oriental", "TM": "Turkmenistán",
    "TN": "Túnez", "TO": "Tonga", "TR": "Turquía", "TT": "Trinidad y Tobago",
    "TV": "Tuvalu", "TW": "Taiwán", "TZ": "Tanzania", "UA": "Ucrania",
    "UG": "Uganda", "US": "Estados Unidos", "UY": "Uruguay", "UZ": "Uzbekistán",
    "VA": "Ciudad del Vaticano", "VC": "San Vicente y las Granadinas",
    "VE": "Venezuela", "VG": "Islas Vírgenes Británicas",
    "VI": "Islas Vírgenes de EE. UU.", "VN": "Vietnam", "VU": "Vanuatu",
    "WS": "Samoa", "YE": "Yemen", "YT": "Mayotte", "ZA": "Sudáfrica",
    "ZM": "Zambia", "ZW": "Zimbabue",
}


def country_name_es(code: str | None) -> str:
    """Nombre en español para un código ISO 3166-1 alpha-2. Si no se conoce
    el código (o viene vacío), se devuelve el código tal cual como respaldo."""
    if not code:
        return "País desconocido"
    return _NAMES_ES.get(code.strip().upper(), code.strip().upper())
