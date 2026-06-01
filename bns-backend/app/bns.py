#data of bns sections for creating embeddings for model training
BNS_SECTION_DETAILS = {
    # Murder and Culpable Homicide (Sections 100-110)
    '100': {
        'crime': 'Murder',
        'title': 'Culpable homicide',
        'description': 'Whoever causes death by doing an act with intention of causing death, or with intention of causing such bodily injury as is likely to cause death, or with knowledge that act is likely to cause death',
        'severity': 'high',
        'punishment': {
            'min': 'Varies based on circumstances',
            'max': 'Life imprisonment or death',
            'fine': 'May also include fine'
        },
        'legal_elements': ['Intention to cause death', 'Intention to cause bodily injury likely to cause death', 'Knowledge of likelihood of death', 'Act causing death'],
        'keywords': ['death', 'homicide', 'intention', 'bodily injury', 'knowledge', 'likely to cause death'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['101', '103', '105', '109'],
        'victim_context': 'Any person whose death is caused',
        'perpetrator_context': 'Person who causes death with requisite intention or knowledge'
    },
    
    '101': {
        'crime': 'Murder',
        'title': 'Murder definition',
        'description': 'Culpable homicide is murder if act done with intention of causing death, or with intention of causing bodily injury known to be likely to cause death, or with intention to cause bodily injury sufficient in ordinary course to cause death, or with knowledge that act is so imminently dangerous that it must in all probability cause death',
        'severity': 'high',
        'punishment': {
            'min': 'Life imprisonment',
            'max': 'Death penalty (in rarest of rare cases)',
            'fine': 'May also include fine'
        },
        'legal_elements': ['Higher degree of intention', 'Premeditation', 'Knowledge of imminent danger', 'Act imminently dangerous to life'],
        'keywords': ['murder', 'death', 'intention', 'premeditation', 'imminent danger', 'bodily injury sufficient to cause death'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['100', '103', '102'],
        'victim_context': 'Person murdered',
        'perpetrator_context': 'Person who commits murder with clear intent and premeditation',
        'exceptions': ['Culpable homicide not amounting to murder (grave and sudden provocation, good faith exceeding right of private defence, public servant exceeding powers)', 'Consent of deceased above 18 years']
    },
    
    '102': {
        'crime': 'Murder',
        'title': 'Transfer of malice - Culpable homicide causing death of person other than intended',
        'description': 'If person causes death to someone unintentionally while aiming at another, liability is determined by what was known or intended about the actual victim',
        'severity': 'high',
        'punishment': {
            'min': 'Same as culpable homicide',
            'max': 'Same as murder if intention/knowledge satisfies murder requirements',
            'fine': 'As applicable'
        },
        'legal_elements': ['Act directed at one person', 'Death caused to another person', 'Transfer of intent', 'Knowledge or intention regarding actual victim'],
        'keywords': ['transferred intent', 'unintended victim', 'wrong person killed', 'misdirected attack'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['100', '101'],
        'victim_context': 'Person killed other than the intended victim',
        'perpetrator_context': 'Person whose act causes death of unintended person'
    },
    
    '103(1)': {
        'crime': 'Murder',
        'title': 'Punishment for murder',
        'description': 'Whoever commits murder shall be punished with death or imprisonment for life and shall also be liable to fine',
        'severity': 'high',
        'punishment': {
            'min': 'Life imprisonment',
            'max': 'Death penalty',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Commission of murder', 'Conviction for murder'],
        'keywords': ['murder punishment', 'death penalty', 'life imprisonment', 'capital punishment'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['101', '103(2)'],
        'victim_context': 'Murdered person',
        'perpetrator_context': 'Convicted murderer'
    },
    
    '103(2)': {
        'crime': 'Murder',
        'title': 'Mob lynching - Murder by group of 5+ on grounds of race, caste, religion',
        'description': 'Murder by group of 5 or more persons acting in concert on grounds of race, caste, sex, place of birth, language, personal belief or any other similar ground',
        'severity': 'high',
        'punishment': {
            'min': 'Life imprisonment',
            'max': 'Death penalty',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Group of 5 or more persons', 'Acting in concert', 'Murder committed', 'Motivated by race, caste, religion, sex, place of birth, language or personal belief'],
        'keywords': ['mob lynching', 'group murder', 'hate crime', 'caste violence', 'religious violence', 'communal violence', 'lynch mob'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['103(1)', '117(4)'],
        'victim_context': 'Person killed due to identity-based hatred',
        'perpetrator_context': 'Member of group of 5+ involved in lynching'
    },
    
    '104': {
        'crime': 'Murder',
        'title': 'Punishment for murder by life-convict',
        'description': 'Murder committed by person under sentence of imprisonment for life shall be punished with death or with imprisonment for life which shall mean imprisonment for remainder of natural life',
        'severity': 'high',
        'punishment': {
            'min': 'Life imprisonment for remainder of natural life',
            'max': 'Death penalty',
            'fine': 'As applicable'
        },
        'legal_elements': ['Accused already serving life imprisonment', 'Murder committed while serving life sentence'],
        'keywords': ['life convict murder', 'prisoner murder', 'murder in custody', 'repeat murderer'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['103'],
        'victim_context': 'Person murdered by life convict',
        'perpetrator_context': 'Person already serving life imprisonment who commits murder'
    },
    
    '105': {
        'crime': 'Murder',
        'title': 'Punishment for culpable homicide not amounting to murder',
        'description': 'Culpable homicide not amounting to murder shall be punished with imprisonment for life or imprisonment up to 10 years and fine',
        'severity': 'high',
        'punishment': {
            'min': 'Imprisonment which may extend to 10 years',
            'max': 'Life imprisonment',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Culpable homicide', 'Not amounting to murder', 'Exceptions under Section 101 applicable'],
        'keywords': ['culpable homicide', 'not murder', 'manslaughter', 'provocation', 'exceeding right of private defence'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['100', '101'],
        'victim_context': 'Person killed in circumstances reducing murder to culpable homicide',
        'perpetrator_context': 'Person guilty of culpable homicide with mitigating circumstances'
    },
    
    '106(1)': {
        'crime': 'Murder',
        'title': 'Causing death by negligence',
        'description': 'Whoever causes death of any person by doing any rash or negligent act not amounting to culpable homicide',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 5 years',
            'max': '5 years imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Rash or negligent act', 'Death caused', 'Not amounting to culpable homicide', 'No criminal intent'],
        'keywords': ['negligent death', 'rash act', 'accidental death', 'negligence', 'carelessness'],
        'cognizable': True,
        'bailable': True,
        'related_sections': ['100', '125'],
        'victim_context': 'Person who died due to negligence',
        'perpetrator_context': 'Person whose negligent act caused death'
    },
    
    '107': {
        'crime': 'Murder',
        'title': 'Abetment of suicide of child or person of unsound mind',
        'description': 'Abetment of suicide of child, person of unsound mind, intoxicated person, or person under duress',
        'severity': 'high',
        'punishment': {
            'min': 'Imprisonment for 10 years',
            'max': 'Life imprisonment',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Abetment of suicide', 'Victim is child or person of unsound mind or intoxicated or under duress'],
        'keywords': ['abetment of suicide', 'child suicide', 'unsound mind', 'vulnerable victim', 'instigating suicide'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['108', '45'],
        'victim_context': 'Child, person of unsound mind, intoxicated person who commits suicide',
        'perpetrator_context': 'Person who abets suicide of vulnerable person'
    },
    
    '108': {
        'crime': 'Murder',
        'title': 'Abetment of suicide',
        'description': 'Abetment of suicide if suicide is committed',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 10 years',
            'max': '10 years imprisonment',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Abetment of suicide', 'Suicide actually committed', 'Causal link between abetment and suicide'],
        'keywords': ['abetment of suicide', 'instigating suicide', 'aiding suicide', 'encouraging suicide'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['107', '45'],
        'victim_context': 'Person who commits suicide',
        'perpetrator_context': 'Person who abets suicide'
    },
    
    '109': {
        'crime': 'Attempt to Murder',
        'title': 'Attempt to murder',
        'description': 'Whoever does any act with such intention or knowledge and under such circumstances that if he caused death he would be guilty of murder',
        'severity': 'high',
        'punishment': {
            'min': 'Imprisonment up to 10 years',
            'max': 'Life imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Act with intention or knowledge', 'Circumstances constitute murder if death caused', 'No death actually caused', 'Attempt made'],
        'keywords': ['attempt to murder', 'attempted killing', 'failed murder', 'intention to kill'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['101', '103', '110'],
        'victim_context': 'Intended victim who survives murder attempt',
        'perpetrator_context': 'Person who attempts to commit murder'
    },
    
    '110': {
        'crime': 'Attempt to Murder',
        'title': 'Attempt to commit culpable homicide',
        'description': 'Whoever does any act with intention or knowledge that if death caused would be guilty of culpable homicide not amounting to murder',
        'severity': 'high',
        'punishment': {
            'min': 'Imprisonment up to 3 years',
            'max': '7 years imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Act with intention or knowledge', 'Would constitute culpable homicide if death caused', 'No actual death', 'Attempt made'],
        'keywords': ['attempt culpable homicide', 'attempted killing', 'failed homicide'],
        'cognizable': True,
        'bailable': True,
        'related_sections': ['100', '105', '109'],
        'victim_context': 'Intended victim who survives',
        'perpetrator_context': 'Person who attempts culpable homicide'
    },
    
    # Sexual Offenses (Sections 63-79)
    '63': {
        'crime': 'Sexual Offense',
        'title': 'Rape definition (consent age raised to 18)',
        'description': 'Man commits rape if he penetrates vagina, mouth, urethra or anus of woman with penis or any object or makes her do so with another person or animal, without consent or with consent obtained by putting her in fear of death or hurt, or with consent when she is of unsound mind or intoxicated, or with consent when she is under 18 years',
        'severity': 'high',
        'punishment': {
            'min': '10 years rigorous imprisonment',
            'max': 'Life imprisonment or death',
            'fine': 'Mandatory fine for victim compensation'
        },
        'legal_elements': ['Penetration (vaginal, oral, urethral, anal)', 'Without consent or invalid consent', 'Consent age 18 years', 'Woman as victim'],
        'keywords': ['rape', 'sexual assault', 'penetration', 'consent', 'sexual violence', 'minor rape', 'age of consent'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['64', '65', '66', '70'],
        'victim_context': 'Woman or girl subjected to rape',
        'perpetrator_context': 'Man who commits rape',
        'exceptions': ['Sexual intercourse by man with his own wife if wife is not under 18 years']
    },
    
    '64': {
        'crime': 'Sexual Offense',
        'title': 'Punishment for rape',
        'description': 'Punishment for rape - rigorous imprisonment not less than 10 years extending to life imprisonment and fine',
        'severity': 'high',
        'punishment': {
            'min': '10 years rigorous imprisonment',
            'max': 'Life imprisonment for remainder of natural life',
            'fine': 'Mandatory fine which shall be just and reasonable to meet medical expenses and rehabilitation'
        },
        'legal_elements': ['Conviction for rape', 'Rigorous imprisonment mandatory'],
        'keywords': ['rape punishment', 'sexual assault penalty', 'imprisonment for rape', 'victim compensation'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['63', '65', '66'],
        'victim_context': 'Rape victim entitled to compensation',
        'perpetrator_context': 'Convicted rapist'
    },
    
    '65(1)': {
        'crime': 'Sexual Offense',
        'title': 'Rape on woman under 16 years',
        'description': 'Rape on woman under 16 years of age - rigorous imprisonment not less than 20 years extending to life imprisonment',
        'severity': 'high',
        'punishment': {
            'min': '20 years rigorous imprisonment',
            'max': 'Life imprisonment for remainder of natural life',
            'fine': 'Mandatory fine for victim compensation'
        },
        'legal_elements': ['Rape', 'Victim under 16 years', 'Enhanced punishment'],
        'keywords': ['child rape', 'minor sexual assault', 'rape of minor', 'child sexual abuse', 'POCSO'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['63', '64', '65(2)'],
        'victim_context': 'Girl child under 16 years',
        'perpetrator_context': 'Man who rapes minor under 16'
    },
    
    '65(2)': {
        'crime': 'Sexual Offense',
        'title': 'Rape on woman under 12 years',
        'description': 'Rape on woman under 12 years - rigorous imprisonment not less than 20 years extending to life imprisonment or death',
        'severity': 'high',
        'punishment': {
            'min': '20 years rigorous imprisonment',
            'max': 'Death penalty or life imprisonment for remainder of natural life',
            'fine': 'Mandatory fine for victim compensation'
        },
        'legal_elements': ['Rape', 'Victim under 12 years', 'Death penalty possible', 'Most heinous form'],
        'keywords': ['child rape', 'rape of child under 12', 'heinous child abuse', 'death penalty for child rape', 'POCSO'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['63', '64', '65(1)'],
        'victim_context': 'Girl child under 12 years',
        'perpetrator_context': 'Man who rapes child under 12'
    },
    
    '66': {
        'crime': 'Sexual Offense',
        'title': 'Causing death or persistent vegetative state of rape victim',
        'description': 'Rape causing death or persistent vegetative state of victim',
        'severity': 'high',
        'punishment': {
            'min': '20 years rigorous imprisonment',
            'max': 'Death penalty or life imprisonment for remainder of natural life',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Rape committed', 'Death caused to victim', 'Or persistent vegetative state caused'],
        'keywords': ['rape murder', 'rape causing death', 'persistent vegetative state', 'fatal rape', 'death during rape'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['63', '64', '70'],
        'victim_context': 'Rape victim who dies or enters persistent vegetative state',
        'perpetrator_context': 'Rapist who causes death or persistent vegetative state'
    },
    
    '67': {
        'crime': 'Sexual Offense',
        'title': 'Sexual intercourse by husband during separation',
        'description': 'Sexual intercourse by husband with wife during separation without consent',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 2 years',
            'max': '2 years imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Judicial separation or separation decree', 'Sexual intercourse by husband', 'Without wife\'s consent'],
        'keywords': ['marital rape during separation', 'separated spouse', 'non-consensual intercourse', 'judicial separation'],
        'cognizable': False,
        'bailable': True,
        'related_sections': ['63'],
        'victim_context': 'Wife living separately under judicial decree',
        'perpetrator_context': 'Husband who has intercourse without consent during separation'
    },
    
    '68': {
        'crime': 'Sexual Offense',
        'title': 'Sexual intercourse by person in authority',
        'description': 'Sexual intercourse by superintendent of jail, remand home, hospital, public servant, manager of hospital, or staff using authority',
        'severity': 'high',
        'punishment': {
            'min': '5 years rigorous imprisonment',
            'max': '10 years rigorous imprisonment',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Person in position of authority', 'Abuse of position', 'Sexual intercourse', 'Woman in custody or under authority'],
        'keywords': ['custodial rape', 'abuse of authority', 'power abuse', 'public servant rape', 'institutional abuse'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['63', '69'],
        'victim_context': 'Woman under custody or authority',
        'perpetrator_context': 'Person in position of authority who abuses power'
    },
    
    '69': {
        'crime': 'Sexual Offense',
        'title': 'Sexual intercourse by deceitful means or false promise of marriage',
        'description': 'Sexual intercourse by employing deceitful means or making false promise of employment or promotion or marriage or inducing belief that man is her husband',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 10 years',
            'max': '10 years imprisonment',
            'fine': 'Mandatory fine for compensation'
        },
        'legal_elements': ['Sexual intercourse', 'Obtained by deceit', 'False promise of marriage or employment', 'Or by impersonation as husband'],
        'keywords': ['rape by deception', 'false promise of marriage', 'deceitful intercourse', 'promise to marry', 'breach of promise'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['63', '68'],
        'victim_context': 'Woman deceived into sexual intercourse',
        'perpetrator_context': 'Person who uses deceit or false promises for sexual intercourse'
    },
    
    '70(1)': {
        'crime': 'Sexual Offense',
        'title': 'Gang rape',
        'description': 'Gang rape by one or more persons constituting group acting in furtherance of common intention on woman',
        'severity': 'high',
        'punishment': {
            'min': '20 years rigorous imprisonment',
            'max': 'Life imprisonment for remainder of natural life',
            'fine': 'Mandatory fine for victim'
        },
        'legal_elements': ['Group of persons', 'Acting in furtherance of common intention', 'Rape committed', 'Woman as victim'],
        'keywords': ['gang rape', 'group rape', 'multiple perpetrators', 'collective sexual violence', 'Nirbhaya case type'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['63', '64', '70(2)', '3(5)'],
        'victim_context': 'Woman subjected to gang rape',
        'perpetrator_context': 'Members of group involved in gang rape'
    },
    
    '70(2)': {
        'crime': 'Sexual Offense',
        'title': 'Gang rape on woman under 18 years',
        'description': 'Gang rape on woman under 18 years of age',
        'severity': 'high',
        'punishment': {
            'min': 'Life imprisonment for remainder of natural life',
            'max': 'Death penalty',
            'fine': 'Mandatory fine for victim'
        },
        'legal_elements': ['Gang rape', 'Victim under 18 years', 'Death penalty possible'],
        'keywords': ['gang rape of minor', 'child gang rape', 'multiple perpetrators on minor', 'group sexual assault on child'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['63', '70(1)', '65'],
        'victim_context': 'Girl under 18 subjected to gang rape',
        'perpetrator_context': 'Members of group involved in gang rape of minor'
    },
    
    '71': {
        'crime': 'Sexual Offense',
        'title': 'Punishment for repeat sexual offenders',
        'description': 'Person previously convicted of rape or certain sexual offenses commits rape or causes death while committing rape',
        'severity': 'high',
        'punishment': {
            'min': 'Life imprisonment for remainder of natural life',
            'max': 'Death penalty',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Previous conviction for rape or sexual offense', 'Commission of rape again', 'Or causing death while committing rape'],
        'keywords': ['repeat rapist', 'serial offender', 'habitual sexual offender', 'second rape conviction'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['63', '64', '66'],
        'victim_context': 'Victim of repeat offender',
        'perpetrator_context': 'Previously convicted sexual offender who reoffends'
    },
    
    '74': {
        'crime': 'Sexual Offense',
        'title': 'Assault with intent to outrage modesty',
        'description': 'Assault or use of criminal force to woman with intent to outrage her modesty',
        'severity': 'medium',
        'punishment': {
            'min': '1 year imprisonment',
            'max': '5 years imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Assault or criminal force', 'Against woman', 'Intent to outrage modesty', 'Without consent'],
        'keywords': ['molestation', 'eve teasing', 'outraging modesty', 'sexual harassment', 'unwanted touching'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['75', '76', '79'],
        'victim_context': 'Woman whose modesty is outraged',
        'perpetrator_context': 'Person who assaults woman to outrage modesty'
    },
    
    '75': {
        'crime': 'Sexual Offense',
        'title': 'Sexual harassment',
        'description': 'Sexual harassment involving unwelcome physical contact or advances, demand for sexual favours, showing pornography, making sexually coloured remarks',
        'severity': 'medium',
        'punishment': {
            'min': '1 year imprisonment',
            'max': '3 years imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Physical contact and advances', 'Demand for sexual favours', 'Showing pornography', 'Making sexually coloured remarks', 'Unwelcome and explicit'],
        'keywords': ['sexual harassment', 'unwelcome advances', 'workplace harassment', 'sexually coloured remarks', 'demand for sexual favours'],
        'cognizable': True,
        'bailable': True,
        'related_sections': ['74', '76', '78'],
        'victim_context': 'Woman subjected to sexual harassment',
        'perpetrator_context': 'Person who sexually harasses woman'
    },
    
    '76': {
        'crime': 'Sexual Offense',
        'title': 'Assault with intent to disrobe (gender neutral)',
        'description': 'Assault or use of criminal force with intent to disrobe or compel to be naked - gender neutral provision',
        'severity': 'medium',
        'punishment': {
            'min': '3 years imprisonment',
            'max': '7 years imprisonment',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Assault or criminal force', 'Intent to disrobe', 'Or compel to be naked', 'Gender neutral'],
        'keywords': ['disrobing', 'stripping', 'forced nudity', 'public humiliation', 'gender neutral offense'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['74', '77'],
        'victim_context': 'Person (man or woman) subjected to disrobing',
        'perpetrator_context': 'Person who attempts to disrobe victim'
    },
    
    '77': {
        'crime': 'Sexual Offense',
        'title': 'Voyeurism (gender neutral)',
        'description': 'Watching or capturing image of woman engaged in private act - gender neutral provision',
        'severity': 'medium',
        'punishment': {
            'min': '1 year imprisonment',
            'max': '3 years imprisonment (first conviction), 7 years (subsequent conviction)',
            'fine': 'May include fine'
        },
        'legal_elements': ['Watching or capturing image', 'Person engaged in private act', 'Without consent', 'Disseminating such images', 'Gender neutral'],
        'keywords': ['voyeurism', 'peeping tom', 'capturing private images', 'invasion of privacy', 'non-consensual photography'],
        'cognizable': True,
        'bailable': True,
        'related_sections': ['75', '78'],
        'victim_context': 'Person whose private moments are captured without consent',
        'perpetrator_context': 'Person who watches or captures private acts'
    },
    
    '78': {
        'crime': 'Sexual Offense',
        'title': 'Stalking',
        'description': 'Following, contacting, monitoring use of internet or electronic communication, watching or spying on person',
        'severity': 'low',
        'punishment': {
            'min': 'Imprisonment up to 3 years',
            'max': '5 years imprisonment (subsequent conviction)',
            'fine': 'May include fine'
        },
        'legal_elements': ['Following or contacting', 'Monitoring internet use', 'Watching or spying', 'Despite clear indication of disinterest', 'Causing fear or alarm'],
        'keywords': ['stalking', 'following', 'cyber stalking', 'monitoring', 'harassment', 'unwanted attention'],
        'cognizable': True,
        'bailable': True,
        'related_sections': ['75', '77'],
        'victim_context': 'Person being stalked',
        'perpetrator_context': 'Person who stalks another'
    },
    
    '79': {
        'crime': 'Sexual Offense',
        'title': 'Word or act to insult modesty',
        'description': 'Uttering word, making sound or gesture, or exhibiting object intending to insult modesty of woman',
        'severity': 'low',
        'punishment': {
            'min': 'Imprisonment up to 1 year',
            'max': '1 year imprisonment',
            'fine': 'Or fine or both'
        },
        'legal_elements': ['Uttering word or making sound', 'Making gesture', 'Exhibiting object', 'Intent to insult modesty', 'Woman as victim'],
        'keywords': ['verbal harassment', 'insulting modesty', 'obscene gesture', 'lewd remarks', 'cat calling'],
        'cognizable': True,
        'bailable': True,
        'related_sections': ['74', '75'],
        'victim_context': 'Woman whose modesty is insulted',
        'perpetrator_context': 'Person who insults woman\'s modesty'
    },
    
    # Theft and Robbery (Sections 303-312)
    '303(2)': {
        'crime': 'Theft or Robbery',
        'title': 'Theft in dwelling house',
        'description': 'Theft in building, tent or vessel used as human dwelling or for custody of property',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 7 years',
            'max': '7 years imprisonment',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Theft', 'In dwelling house or tent or vessel', 'Used for human dwelling or custody of property'],
        'keywords': ['house theft', 'burglary', 'residential theft', 'dwelling house', 'home invasion'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['303', '304', '305'],
        'victim_context': 'Owner of dwelling or property',
        'perpetrator_context': 'Thief who commits theft in dwelling'
    },
    
    '304': {
        'crime': 'Theft or Robbery',
        'title': 'Snatching (newly added distinct from theft)',
        'description': 'Theft by suddenly or quickly or forcibly seizing or securing or grabbing or taking away moveable property from person or his possession',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 3 years',
            'max': '3 years imprisonment',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Theft', 'Suddenly or quickly or forcibly', 'Seizing moveable property', 'From person or possession'],
        'keywords': ['snatching', 'chain snatching', 'mobile snatching', 'purse snatching', 'grabbing', 'forcible taking'],
        'cognizable': True,
        'bailable': True,
        'related_sections': ['303', '309'],
        'victim_context': 'Person from whom property is snatched',
        'perpetrator_context': 'Person who snatches property'
    },
    
    '305': {
        'crime': 'Theft or Robbery',
        'title': 'Theft by clerk or servant of property',
        'description': 'Theft of property in possession of master by clerk or servant',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 7 years',
            'max': '7 years imprisonment',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Theft', 'Property of master', 'By clerk or servant', 'Breach of trust element'],
        'keywords': ['employee theft', 'servant theft', 'workplace theft', 'breach of trust', 'embezzlement'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['303', '316'],
        'victim_context': 'Master or employer',
        'perpetrator_context': 'Clerk or servant who steals from master'
    },
    
    '306': {
        'crime': 'Theft or Robbery',
        'title': 'Robbery',
        'description': 'Theft or extortion where offender voluntarily causes or attempts to cause death, hurt or wrongful restraint or fear of instant death, hurt or restraint',
        'severity': 'high',
        'punishment': {
            'min': 'Rigorous imprisonment up to 10 years',
            'max': '10 years rigorous imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Theft or extortion', 'Voluntary causing or attempt to cause death, hurt or wrongful restraint', 'Fear of instant death, hurt or restraint'],
        'keywords': ['robbery', 'armed robbery', 'violent theft', 'extortion with violence', 'threatening theft'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['303', '309', '310'],
        'victim_context': 'Person robbed with violence or threat',
        'perpetrator_context': 'Robber who uses violence or threat'
    },
    
    '309(2)': {
        'crime': 'Theft or Robbery',
        'title': 'Robbery or dacoity with attempt to cause death or grievous hurt',
        'description': 'Robbery or dacoity with attempt to cause death or grievous hurt',
        'severity': 'high',
        'punishment': {
            'min': 'Rigorous imprisonment for 7 years',
            'max': 'Life imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Robbery or dacoity', 'Attempt to cause death or grievous hurt', 'Use of deadly weapon'],
        'keywords': ['violent robbery', 'armed dacoity', 'robbery with weapon', 'attempt to kill during robbery'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['309', '310', '311'],
        'victim_context': 'Victim of violent robbery',
        'perpetrator_context': 'Robber who attempts to cause death or grievous hurt'
    },
    
    '310(2)': {
        'crime': 'Theft or Robbery',
        'title': 'Dacoity with murder',
        'description': 'Dacoity where one of persons committing dacoity commits murder in committing dacoity',
        'severity': 'high',
        'punishment': {
            'min': '10 years rigorous imprisonment',
            'max': 'Death penalty or life imprisonment',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Dacoity', 'Murder committed', 'During commission of dacoity', 'All members liable'],
        'keywords': ['dacoity with murder', 'fatal robbery', 'killing during dacoity', 'group robbery murder'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['310', '311', '103'],
        'victim_context': 'Person murdered during dacoity',
        'perpetrator_context': 'Member of dacoity group where murder occurs'
    },
    
    '311': {
        'crime': 'Theft or Robbery',
        'title': 'Dacoity',
        'description': 'Robbery by five or more persons conjointly committing or attempting to commit robbery',
        'severity': 'high',
        'punishment': {
            'min': 'Rigorous imprisonment up to 10 years',
            'max': 'Life imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Five or more persons', 'Conjointly committing', 'Robbery or attempt'],
        'keywords': ['dacoity', 'gang robbery', 'organized robbery', 'group of robbers', 'five or more'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['309', '310', '306'],
        'victim_context': 'Victim of gang robbery',
        'perpetrator_context': 'Member of group of 5+ committing robbery'
    },
    
    '312': {
        'crime': 'Theft or Robbery',
        'title': 'Snatching (newly added distinct from theft)',
        'description': 'Theft is snatching if offender suddenly or quickly or forcibly seizes moveable property from person',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 3 years',
            'max': '3 years imprisonment',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Sudden or quick or forcible seizure', 'Moveable property', 'From person or possession'],
        'keywords': ['snatching', 'quick theft', 'forcible taking', 'grabbing', 'seizing property'],
        'cognizable': True,
        'bailable': True,
        'related_sections': ['303', '304', '309'],
        'victim_context': 'Person from whom property is snatched',
        'perpetrator_context': 'Snatcher'
    },
    
    # Fraud and Cheating (Sections 316-340)
    '316(1)': {
        'crime': 'Fraud or Cheating',
        'title': 'Cheating',
        'description': 'Whoever by deceiving any person fraudulently or dishonestly induces person to deliver property or consent that any person shall retain property',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 1 year',
            'max': '1 year imprisonment or fine or both',
            'fine': 'May include fine'
        },
        'legal_elements': ['Deception', 'Fraudulent or dishonest inducement', 'Delivery of property or consent to retain property'],
        'keywords': ['cheating', 'fraud', 'deception', 'dishonest inducement', 'fraudulent delivery'],
        'cognizable': True,
        'bailable': True,
        'related_sections': ['316(2)', '318', '319'],
        'victim_context': 'Person deceived into parting with property',
        'perpetrator_context': 'Person who cheats by deception'
    },
    
    '316(2)': {
        'crime': 'Fraud or Cheating',
        'title': 'Cheating by personation',
        'description': 'Person cheats by personation if he cheats by pretending to be some other person or by knowingly substituting one person for another',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 3 years',
            'max': '3 years imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Cheating', 'Personation', 'Pretending to be another person', 'Substituting one person for another'],
        'keywords': ['impersonation', 'identity fraud', 'pretending to be someone else', 'substitution fraud'],
        'cognizable': True,
        'bailable': True,
        'related_sections': ['316(1)', '319'],
        'victim_context': 'Person deceived by impersonation',
        'perpetrator_context': 'Person who impersonates another to cheat'
    },
    
    '318': {
        'crime': 'Fraud or Cheating',
        'title': 'Cheating and dishonestly inducing delivery of property',
        'description': 'Cheating and dishonestly inducing delivery of property, making or altering valuable security',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 3 years',
            'max': '7 years imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Cheating', 'Dishonest inducement', 'Delivery of property', 'Or making/altering valuable security'],
        'keywords': ['property fraud', 'inducing delivery', 'valuable security', 'dishonest cheating'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['316', '319'],
        'victim_context': 'Person who parts with property through cheating',
        'perpetrator_context': 'Person who cheats to obtain property'
    },
    
    '319': {
        'crime': 'Cyber Crime',
        'title': 'Cheating by personation using computer resource',
        'description': 'Cheating by personation by using computer resource or communication device',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 3 years',
            'max': '3 years imprisonment',
            'fine': 'May include fine up to Rs 1 lakh'
        },
        'legal_elements': ['Cheating by personation', 'Using computer resource', 'Or communication device', 'Electronic fraud'],
        'keywords': ['cyber fraud', 'online cheating', 'phishing', 'computer fraud', 'electronic impersonation', 'identity theft online'],
        'cognizable': True,
        'bailable': True,
        'related_sections': ['316', '318'],
        'victim_context': 'Person cheated through computer/online means',
        'perpetrator_context': 'Person who uses computer resources for cheating'
    },
    
    '336': {
        'crime': 'Fraud or Cheating',
        'title': 'Forgery',
        'description': 'Making false document or false electronic record with intent to cause damage or injury or to support claim or title or to cause any person to part with property',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 2 years',
            'max': '2 years imprisonment',
            'fine': 'Or fine or both'
        },
        'legal_elements': ['Making false document', 'Intent to cause damage or injury', 'Or to support claim', 'Or to cause to part with property'],
        'keywords': ['forgery', 'false document', 'fake document', 'forged signature', 'document fraud'],
        'cognizable': True,
        'bailable': True,
        'related_sections': ['338', '340'],
        'victim_context': 'Person affected by forged document',
        'perpetrator_context': 'Person who forges document'
    },
    
    '338': {
        'crime': 'Fraud or Cheating',
        'title': 'Forgery for purpose of cheating',
        'description': 'Forgery for purpose of cheating',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 7 years',
            'max': '7 years imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Forgery', 'Purpose of cheating', 'Intent to defraud'],
        'keywords': ['forgery for cheating', 'fraudulent forgery', 'document fraud for deception'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['336', '316', '340'],
        'victim_context': 'Person cheated through forged document',
        'perpetrator_context': 'Person who forges document to cheat'
    },
    
    '340': {
        'crime': 'Fraud or Cheating',
        'title': 'Forgery of valuable security or will',
        'description': 'Forgery of valuable security, will or authority to make or transfer valuable security',
        'severity': 'high',
        'punishment': {
            'min': 'Imprisonment up to 7 years',
            'max': 'Life imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Forgery', 'Of valuable security', 'Or will', 'Or authority to transfer'],
        'keywords': ['forged will', 'valuable security forgery', 'financial document fraud', 'testament forgery'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['336', '338'],
        'victim_context': 'Beneficiary or owner of valuable security or will',
        'perpetrator_context': 'Person who forges valuable security or will'
    },
    
    # Kidnapping and Abduction (Sections 137-146)
    '137(1)': {
        'crime': 'Kidnapping',
        'title': 'Kidnapping from India or lawful guardianship',
        'description': 'Kidnapping any person from India or from lawful guardianship',
        'severity': 'high',
        'punishment': {
            'min': 'Imprisonment up to 7 years',
            'max': '7 years imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Taking or enticing', 'Person from India or lawful guardianship', 'Without consent'],
        'keywords': ['kidnapping', 'abduction', 'taking person', 'guardian consent', 'unlawful taking'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['138', '139', '140'],
        'victim_context': 'Person kidnapped',
        'perpetrator_context': 'Person who kidnaps'
    },
    
    '137(1)(b)': {
        'crime': 'Kidnapping',
        'title': 'Kidnapping child from lawful guardianship (gender neutral)',
        'description': 'Kidnapping or abducting child under 18 years from lawful guardianship - gender neutral provision',
        'severity': 'high',
        'punishment': {
            'min': 'Imprisonment up to 7 years',
            'max': '7 years imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Taking or enticing', 'Child under 18 years', 'From lawful guardianship', 'Without guardian consent', 'Gender neutral'],
        'keywords': ['child kidnapping', 'minor abduction', 'parental kidnapping', 'child stealing', 'gender neutral'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['137', '139', '140'],
        'victim_context': 'Child under 18 kidnapped from guardian',
        'perpetrator_context': 'Person who kidnaps child'
    },
    
    '137(2)': {
        'crime': 'Kidnapping',
        'title': 'Punishment for kidnapping',
        'description': 'Punishment for kidnapping from India or from lawful guardianship',
        'severity': 'high',
        'punishment': {
            'min': 'Imprisonment up to 7 years',
            'max': '7 years imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Conviction for kidnapping', 'Under Section 137(1)'],
        'keywords': ['kidnapping punishment', 'abduction penalty'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['137(1)'],
        'victim_context': 'Kidnapped person',
        'perpetrator_context': 'Convicted kidnapper'
    },
    
    '138': {
        'crime': 'Kidnapping',
        'title': 'Abduction',
        'description': 'Abduction by force compelling or by deceitful means inducing person to go from any place',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 7 years',
            'max': '7 years imprisonment or fine or both',
            'fine': 'May include fine'
        },
        'legal_elements': ['Forcing or compelling', 'Or deceitful inducement', 'Person to go from place'],
        'keywords': ['abduction', 'forcible taking', 'deceitful inducement', 'unlawful removal'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['137', '140'],
        'victim_context': 'Person abducted',
        'perpetrator_context': 'Person who abducts by force or deceit'
    },
    
    '139': {
        'crime': 'Kidnapping',
        'title': 'Kidnapping or maiming child for begging',
        'description': 'Kidnapping or obtaining custody of child to employ or use for purposes of begging, or maiming child for begging',
        'severity': 'high',
        'punishment': {
            'min': 'Rigorous imprisonment for 10 years',
            'max': 'Life imprisonment',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Kidnapping child', 'Or obtaining custody', 'For begging purposes', 'Or maiming for begging'],
        'keywords': ['child begging', 'maiming child', 'forced begging', 'child exploitation', 'begging racket'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['137', '143', '144'],
        'victim_context': 'Child kidnapped or maimed for begging',
        'perpetrator_context': 'Person who kidnaps or maims child for begging'
    },
    
    '140(1)': {
        'crime': 'Kidnapping',
        'title': 'Kidnapping or abducting to murder',
        'description': 'Kidnapping or abducting person in order that person may be murdered or disposed of to be put in danger of being murdered',
        'severity': 'high',
        'punishment': {
            'min': 'Rigorous imprisonment up to 10 years',
            'max': 'Life imprisonment',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Kidnapping or abduction', 'Intent that person be murdered', 'Or disposed to be in danger of murder'],
        'keywords': ['kidnapping for murder', 'abduction to kill', 'murder intent', 'human sacrifice'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['137', '140(2)', '103'],
        'victim_context': 'Person kidnapped to be murdered',
        'perpetrator_context': 'Person who kidnaps for murder'
    },
    
    '140(2)': {
        'crime': 'Kidnapping',
        'title': 'Kidnapping for ransom',
        'description': 'Kidnapping or keeping person in detention threatening death or hurt to compel Government or any person to do or abstain from doing act or to pay ransom',
        'severity': 'high',
        'punishment': {
            'min': 'Life imprisonment',
            'max': 'Death penalty',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Kidnapping or detention', 'Threatening death or hurt', 'To compel Government or person', 'To pay ransom or do act'],
        'keywords': ['kidnapping for ransom', 'hostage taking', 'ransom demand', 'threatening for money', 'extortionate kidnapping'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['137', '140(1)', '308'],
        'victim_context': 'Person kidnapped and held for ransom',
        'perpetrator_context': 'Person who kidnaps for ransom'
    },
    
    '140(3)': {
        'crime': 'Kidnapping',
        'title': 'Kidnapping with intent to secretly and wrongfully confine',
        'description': 'Kidnapping or abducting person with intent to secretly and wrongfully confine',
        'severity': 'high',
        'punishment': {
            'min': 'Imprisonment up to 7 years',
            'max': '7 years imprisonment',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Kidnapping or abduction', 'Intent to secretly confine', 'Wrongful confinement'],
        'keywords': ['secret confinement', 'wrongful confinement', 'unlawful detention', 'hidden captivity'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['137', '140'],
        'victim_context': 'Person kidnapped to be secretly confined',
        'perpetrator_context': 'Person who kidnaps for confinement'
    },
    
    '140(4)': {
        'crime': 'Kidnapping',
        'title': 'Kidnapping to subject to grievous hurt, slavery, etc',
        'description': 'Kidnapping or abducting person to subject to grievous hurt, slavery, or unnatural lust, or knowing it is likely person will be so subjected',
        'severity': 'high',
        'punishment': {
            'min': 'Imprisonment up to 10 years',
            'max': '10 years imprisonment',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Kidnapping or abduction', 'To subject to grievous hurt, slavery or unnatural lust', 'Or knowledge of such likelihood'],
        'keywords': ['kidnapping for slavery', 'sexual exploitation', 'forced labor', 'grievous hurt', 'unnatural lust'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['137', '143', '144'],
        'victim_context': 'Person kidnapped for exploitation',
        'perpetrator_context': 'Person who kidnaps for exploitation'
    },
    
    '143': {
        'crime': 'Kidnapping',
        'title': 'Trafficking of person',
        'description': 'Recruiting, transporting, harboring, transferring or receiving person by threat, force, coercion, abduction, fraud, deception, abuse of power, or inducement for exploitation',
        'severity': 'high',
        'punishment': {
            'min': 'Rigorous imprisonment for 7 years',
            'max': 'Life imprisonment',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Recruiting, transporting, harboring, transferring, receiving', 'By threat, force, coercion, fraud', 'For exploitation'],
        'keywords': ['human trafficking', 'sex trafficking', 'forced labor', 'exploitation', 'slavery', 'bonded labor'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['144', '139', '140'],
        'victim_context': 'Person trafficked for exploitation',
        'perpetrator_context': 'Trafficker who recruits or transports persons'
    },
    
    '144': {
        'crime': 'Kidnapping',
        'title': 'Exploitation of trafficked person',
        'description': 'Exploitation of trafficked person for physical exploitation, slavery, servitude, forced removal of organs, forced labor, drug peddling, prostitution',
        'severity': 'high',
        'punishment': {
            'min': 'Rigorous imprisonment for 5 years',
            'max': '7 years rigorous imprisonment',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Exploitation of trafficked person', 'Physical exploitation, slavery, forced labor', 'Prostitution, organ removal'],
        'keywords': ['trafficking exploitation', 'forced prostitution', 'organ trafficking', 'bonded labor', 'sex slavery'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['143'],
        'victim_context': 'Trafficked person being exploited',
        'perpetrator_context': 'Person who exploits trafficked person'
    },
    
    # Dowry and Domestic Violence (Sections 80, 85-86)
    '80': {
        'crime': 'Dowry Harassment',
        'title': 'Dowry death',
        'description': 'Woman death caused by burns or bodily injury or occurs otherwise than under normal circumstances within 7 years of marriage where she was subjected to cruelty or harassment by husband or relative in connection with demand for dowry',
        'severity': 'high',
        'punishment': {
            'min': 'Imprisonment for 7 years',
            'max': 'Life imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Death of woman', 'Within 7 years of marriage', 'By burns or bodily injury or abnormal circumstances', 'Cruelty or harassment for dowry'],
        'keywords': ['dowry death', 'bride burning', 'dowry harassment', 'marriage death', 'cruelty for dowry'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['85', '86'],
        'victim_context': 'Woman who dies due to dowry harassment',
        'perpetrator_context': 'Husband or relative who causes dowry death'
    },
    
    '85': {
        'crime': 'Dowry Harassment',
        'title': 'Husband or relative subjecting woman to cruelty',
        'description': 'Husband or relative of husband subjecting woman to cruelty',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 3 years',
            'max': '3 years imprisonment',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Husband or relative', 'Subjecting woman to cruelty', 'As defined in Section 86'],
        'keywords': ['domestic violence', 'cruelty to wife', 'marital cruelty', 'in-law harassment', 'dowry harassment'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['80', '86'],
        'victim_context': 'Woman subjected to cruelty by husband or relatives',
        'perpetrator_context': 'Husband or relative who subjects woman to cruelty'
    },
    
    '86': {
        'crime': 'Dowry Harassment',
        'title': 'Cruelty defined',
        'description': 'Cruelty means willful conduct likely to drive woman to commit suicide or cause grave injury or danger to life, limb or health; or harassment for dowry demand',
        'severity': 'medium',
        'punishment': {
            'min': 'As per Section 85',
            'max': 'As per Section 85',
            'fine': 'As per Section 85'
        },
        'legal_elements': ['Willful conduct', 'Likely to drive to suicide or cause grave injury', 'Or harassment for dowry'],
        'keywords': ['cruelty definition', 'dowry harassment', 'driving to suicide', 'grave injury', 'mental cruelty'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['85', '80'],
        'victim_context': 'Woman subjected to defined cruelty',
        'perpetrator_context': 'Person who commits defined cruelty'
    },
    
    # Assault and Hurt (Sections 114-125)
    '114': {
        'crime': 'Assault',
        'title': 'Hurt',
        'description': 'Whoever causes bodily pain, disease or infirmity to any person',
        'severity': 'low',
        'punishment': {
            'min': 'Imprisonment up to 1 year or fine up to Rs 1000 or both',
            'max': '1 year imprisonment or Rs 1000 fine or both',
            'fine': 'May include fine up to Rs 1000'
        },
        'legal_elements': ['Causing bodily pain', 'Disease', 'Infirmity'],
        'keywords': ['hurt', 'bodily pain', 'injury', 'causing pain', 'assault'],
        'cognizable': True,
        'bailable': True,
        'related_sections': ['115', '116', '117'],
        'victim_context': 'Person who suffers hurt',
        'perpetrator_context': 'Person who causes hurt'
    },
    
    '115(1)': {
        'crime': 'Assault',
        'title': 'Voluntarily causing hurt',
        'description': 'Whoever does act with intention of causing hurt to any person or with knowledge that he is likely to cause hurt',
        'severity': 'low',
        'punishment': {
            'min': 'Imprisonment up to 1 year or fine up to Rs 1000 or both',
            'max': '1 year imprisonment or Rs 1000 fine or both',
            'fine': 'May include fine up to Rs 1000'
        },
        'legal_elements': ['Act with intention to cause hurt', 'Or knowledge likely to cause hurt', 'Hurt actually caused'],
        'keywords': ['voluntary hurt', 'intentional hurt', 'assault with intent', 'knowingly causing pain'],
        'cognizable': True,
        'bailable': True,
        'related_sections': ['114', '115(2)', '117'],
        'victim_context': 'Person intentionally hurt',
        'perpetrator_context': 'Person who voluntarily causes hurt'
    },
    
    '115(2)': {
        'crime': 'Assault',
        'title': 'Punishment for voluntarily causing hurt',
        'description': 'Punishment for voluntarily causing hurt',
        'severity': 'low',
        'punishment': {
            'min': 'Imprisonment up to 1 year or fine up to Rs 1000 or both',
            'max': '1 year imprisonment or Rs 1000 fine or both',
            'fine': 'May include fine up to Rs 1000'
        },
        'legal_elements': ['Conviction for voluntarily causing hurt'],
        'keywords': ['hurt punishment', 'assault penalty'],
        'cognizable': True,
        'bailable': True,
        'related_sections': ['115(1)'],
        'victim_context': 'Victim of voluntary hurt',
        'perpetrator_context': 'Convicted for causing hurt'
    },
    
    '116': {
        'crime': 'Assault',
        'title': 'Grievous hurt (reduced from 20 to 15 days)',
        'description': 'Grievous hurt includes emasculation, permanent privation of sight, permanent privation of hearing, privation of any member or joint, destruction of permanent impairing of powers of any member or joint, permanent disfiguration of head or face, fracture or dislocation of bone or tooth, or any hurt endangering life or causing person to be unable to follow ordinary pursuits for 15 days (reduced from 20)',
        'severity': 'medium',
        'punishment': {
            'min': 'As per specific sections',
            'max': 'As per specific sections',
            'fine': 'As applicable'
        },
        'legal_elements': ['One of 8 types of injuries listed', 'Or endangering life', 'Or 15+ days inability to work'],
        'keywords': ['grievous hurt', 'serious injury', 'permanent injury', 'disfigurement', 'fracture', 'loss of member'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['117', '118'],
        'victim_context': 'Person suffering grievous hurt',
        'perpetrator_context': 'Person who causes grievous hurt'
    },
    
    '117(1)': {
        'crime': 'Assault',
        'title': 'Voluntarily causing grievous hurt',
        'description': 'Whoever voluntarily causes grievous hurt',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 7 years',
            'max': '7 years imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Voluntary act', 'Causing grievous hurt', 'Intention or knowledge'],
        'keywords': ['grievous hurt', 'serious assault', 'intentional serious injury', 'voluntary grievous hurt'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['116', '117(2)', '117(3)'],
        'victim_context': 'Person suffering voluntary grievous hurt',
        'perpetrator_context': 'Person who voluntarily causes grievous hurt'
    },
    
    '117(2)': {
        'crime': 'Assault',
        'title': 'Punishment for voluntarily causing grievous hurt',
        'description': 'Punishment for voluntarily causing grievous hurt',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 7 years',
            'max': '7 years imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Conviction for voluntarily causing grievous hurt'],
        'keywords': ['grievous hurt punishment', 'serious assault penalty'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['117(1)'],
        'victim_context': 'Victim of grievous hurt',
        'perpetrator_context': 'Convicted for causing grievous hurt'
    },
    
    '117(3)': {
        'crime': 'Assault',
        'title': 'Causing permanent disability or persistent vegetative state',
        'description': 'Voluntarily causing grievous hurt resulting in permanent or likely permanent disability or persistent vegetative state',
        'severity': 'high',
        'punishment': {
            'min': 'Rigorous imprisonment for 10 years',
            'max': 'Life imprisonment',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Grievous hurt', 'Resulting in permanent disability', 'Or persistent vegetative state'],
        'keywords': ['permanent disability', 'persistent vegetative state', 'permanent injury', 'life-altering injury', 'severe disability'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['117(1)', '116'],
        'victim_context': 'Person left permanently disabled or in vegetative state',
        'perpetrator_context': 'Person who causes permanent disability'
    },
    
    '117(4)': {
        'crime': 'Assault',
        'title': 'Group of 5+ causing grievous hurt on grounds of caste/religion',
        'description': 'Voluntarily causing grievous hurt by group of 5 or more persons on grounds of race, caste, sex, place of birth, language, personal belief',
        'severity': 'high',
        'punishment': {
            'min': 'Rigorous imprisonment for 7 years',
            'max': 'Life imprisonment',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Group of 5 or more', 'Causing grievous hurt', 'On grounds of identity', 'Hate crime element'],
        'keywords': ['hate crime', 'mob violence', 'caste violence', 'communal violence', 'group assault', 'lynching'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['117(1)', '103(2)'],
        'victim_context': 'Person assaulted by mob due to identity',
        'perpetrator_context': 'Member of group causing grievous hurt'
    },
    
    '118(1)': {
        'crime': 'Assault',
        'title': 'Voluntarily causing hurt by dangerous weapons',
        'description': 'Voluntarily causing hurt by dangerous weapons or means',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 3 years or fine or both',
            'max': '3 years imprisonment or fine or both',
            'fine': 'May include fine'
        },
        'legal_elements': ['Voluntarily causing hurt', 'By dangerous weapon or means', 'Includes fire, heated substance, poison, corrosive substance, explosive'],
        'keywords': ['weapon assault', 'dangerous weapon', 'armed assault', 'hurt by weapon'],
        'cognizable': True,
        'bailable': True,
        'related_sections': ['115', '118(2)'],
        'victim_context': 'Person hurt by dangerous weapon',
        'perpetrator_context': 'Person who uses weapon to cause hurt'
    },
    
    '118(2)': {
        'crime': 'Assault',
        'title': 'Voluntarily causing grievous hurt by dangerous weapons',
        'description': 'Voluntarily causing grievous hurt by dangerous weapons or means',
        'severity': 'high',
        'punishment': {
            'min': 'Imprisonment for 3 years',
            'max': 'Life imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Voluntarily causing grievous hurt', 'By dangerous weapon or means', 'Enhanced punishment'],
        'keywords': ['grievous hurt by weapon', 'armed assault', 'dangerous weapon grievous hurt', 'weapon violence'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['117', '118(1)'],
        'victim_context': 'Person suffering grievous hurt from weapon',
        'perpetrator_context': 'Person who uses weapon to cause grievous hurt'
    },
    
    '124(1)': {
        'crime': 'Assault',
        'title': 'Causing grievous hurt by acid attack',
        'description': 'Voluntarily causing grievous hurt by use of acid',
        'severity': 'high',
        'punishment': {
            'min': 'Rigorous imprisonment for 10 years',
            'max': 'Life imprisonment',
            'fine': 'Mandatory fine with reasonable amount for medical expenses and rehabilitation'
        },
        'legal_elements': ['Voluntarily causing grievous hurt', 'By use of acid or similar corrosive substance', 'Permanent or likely permanent damage to body'],
        'keywords': ['acid attack', 'acid throwing', 'corrosive attack', 'disfigurement by acid', 'chemical attack'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['124(2)', '117'],
        'victim_context': 'Victim of acid attack',
        'perpetrator_context': 'Person who throws acid'
    },
    
    '124(2)': {
        'crime': 'Assault',
        'title': 'Throwing or attempting to throw acid',
        'description': 'Throwing or attempting to throw acid or administering acid to person with intention of causing hurt',
        'severity': 'high',
        'punishment': {
            'min': 'Rigorous imprisonment for 5 years',
            'max': '7 years rigorous imprisonment',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Throwing or attempting to throw acid', 'Or administering acid', 'With intention to cause hurt or knowledge of likelihood'],
        'keywords': ['acid throwing attempt', 'attempting acid attack', 'acid threat', 'corrosive substance'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['124(1)'],
        'victim_context': 'Person targeted in acid attack attempt',
        'perpetrator_context': 'Person who attempts acid attack'
    },
    
    '125': {
        'crime': 'Assault',
        'title': 'Act endangering life or personal safety',
        'description': 'Act so rashly or negligently as to endanger human life or personal safety of others',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 3 months or fine up to Rs 250 or both',
            'max': '3 months imprisonment or Rs 250 fine or both',
            'fine': 'May include fine up to Rs 250'
        },
        'legal_elements': ['Rash or negligent act', 'Endangering human life or personal safety', 'No actual hurt caused'],
        'keywords': ['rash act', 'negligent act', 'endangering life', 'public safety', 'negligence'],
        'cognizable': True,
        'bailable': True,
        'related_sections': ['106', '114'],
        'victim_context': 'Person endangered by rash or negligent act',
        'perpetrator_context': 'Person who acts rashly or negligently'
    },
    
    # Extortion and Criminal Intimidation (Sections 308-309, 351-352)
    '308': {
        'crime': 'Extortion',
        'title': 'Extortion',
        'description': 'Intentionally putting person in fear of injury to person, reputation or property to dishonestly induce person to deliver property or valuable security',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 3 years or fine or both',
            'max': '3 years imprisonment or fine or both',
            'fine': 'May include fine'
        },
        'legal_elements': ['Putting in fear of injury', 'To person, reputation or property', 'Dishonest inducement', 'To deliver property or valuable security'],
        'keywords': ['extortion', 'blackmail', 'threatening for money', 'fear of injury', 'dishonest inducement'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['309', '351', '140(2)'],
        'victim_context': 'Person extorted through fear',
        'perpetrator_context': 'Person who extorts'
    },
    
    '309': {
        'crime': 'Extortion',
        'title': 'Extortion by putting in fear of death or grievous hurt',
        'description': 'Extortion by putting person in fear of death or grievous hurt to person or another',
        'severity': 'high',
        'punishment': {
            'min': 'Imprisonment up to 10 years',
            'max': '10 years imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Extortion', 'By putting in fear of death or grievous hurt'],
        'keywords': ['severe extortion', 'death threats', 'grievous hurt threats', 'serious blackmail'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['308', '306'],
        'victim_context': 'Person extorted with death or grievous hurt threats',
        'perpetrator_context': 'Person who extorts with serious threats'
    },
    
    '351': {
        'crime': 'Extortion',
        'title': 'Criminal intimidation',
        'description': 'Threatening person with injury to person, reputation or property to cause alarm or to cause person to do act or omit to do act',
        'severity': 'low',
        'punishment': {
            'min': 'Imprisonment up to 2 years or fine or both',
            'max': '2 years imprisonment or fine or both',
            'fine': 'May include fine'
        },
        'legal_elements': ['Threatening with injury', 'To person, reputation or property', 'To cause alarm', 'Or to compel act or omission'],
        'keywords': ['intimidation', 'threatening', 'criminal threat', 'coercion', 'menacing'],
        'cognizable': True,
        'bailable': True,
        'related_sections': ['352', '308'],
        'victim_context': 'Person criminally intimidated',
        'perpetrator_context': 'Person who criminally intimidates'
    },
    
    '352': {
        'crime': 'Extortion',
        'title': 'Criminal intimidation by anonymous communication',
        'description': 'Criminal intimidation by anonymous communication or having taken precaution to conceal name or abode',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment up to 2 years',
            'max': '2 years imprisonment',
            'fine': 'May include fine'
        },
        'legal_elements': ['Criminal intimidation', 'By anonymous communication', 'Or concealment of identity'],
        'keywords': ['anonymous threats', 'concealed identity', 'anonymous intimidation', 'hidden threat'],
        'cognizable': True,
        'bailable': True,
        'related_sections': ['351'],
        'victim_context': 'Person intimidated anonymously',
        'perpetrator_context': 'Person who intimidates anonymously'
    },
    
    # Organized Crime and Terrorism (Sections 111-113)
    '111': {
        'crime': 'Others',
        'title': 'Organised crime (NEW - kidnapping, robbery, extortion, land grabbing)',
        'description': 'Organised crime including kidnapping, robbery, vehicle theft, extortion, land grabbing, contract killing, economic offences, cyber-crimes, trafficking, committed by individuals acting in concert as member of organised crime syndicate using violence, threat, intimidation, coercion',
        'severity': 'high',
        'punishment': {
            'min': 'Imprisonment for 5 years with minimum fine of Rs 5 lakh',
            'max': 'Death penalty or life imprisonment with minimum fine of Rs 10 lakh (if death results)',
            'fine': 'Minimum Rs 5 lakh, Rs 10 lakh if death'
        },
        'legal_elements': ['Unlawful activities listed', 'By individuals in concert', 'As member or on behalf of organised crime syndicate', 'Using violence, threat, intimidation or coercion', 'For material or financial benefit'],
        'keywords': ['organised crime', 'syndicate', 'mafia', 'gang', 'racketeering', 'contract killing', 'land grabbing', 'cyber crime ring'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['112', '113'],
        'victim_context': 'Victim of organised crime',
        'perpetrator_context': 'Member of organised crime syndicate',
        'note': 'New provision not in IPC'
    },
    
    '112': {
        'crime': 'Others',
        'title': 'Petty organised crime (NEW - gang theft, snatching, cheating)',
        'description': 'Petty organised crime including theft, snatching, cheating, unauthorised selling of tickets, betting and gambling, selling of public exam papers, hawala and illicit foreign exchange, for commercial purpose for gain, by member of organised crime syndicate',
        'severity': 'medium',
        'punishment': {
            'min': 'Imprisonment for 1 year with minimum fine of Rs 1 lakh',
            'max': '7 years imprisonment with minimum fine of Rs 1 lakh',
            'fine': 'Minimum Rs 1 lakh'
        },
        'legal_elements': ['Petty organised crimes listed', 'For commercial purpose', 'For gain', 'By member of organised crime syndicate'],
        'keywords': ['petty organised crime', 'gang theft', 'organised snatching', 'ticket touting', 'hawala', 'exam paper leaks', 'organised betting'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['111'],
        'victim_context': 'Victim of petty organised crime',
        'perpetrator_context': 'Member of petty organised crime syndicate',
        'note': 'New provision not in IPC'
    },
    
    '113': {
        'crime': 'Others',
        'title': 'Terrorist act (NEW)',
        'description': 'Act with intent to threaten unity, integrity, sovereignty, security or economic security of India or to strike terror in people, involving murder, grievous hurt, kidnapping, destruction of property, disruption of supplies or services, damage to monetary systems, cyber terrorism',
        'severity': 'high',
        'punishment': {
            'min': 'Imprisonment for 5 years with fine',
            'max': 'Death penalty or life imprisonment (if death results)',
            'fine': 'Mandatory fine'
        },
        'legal_elements': ['Act with terrorist intent', 'To threaten unity, integrity, sovereignty, security', 'Or to strike terror', 'Involving serious crimes listed'],
        'keywords': ['terrorism', 'terrorist act', 'terror attack', 'national security', 'anti-national', 'sabotage', 'cyber terrorism'],
        'cognizable': True,
        'bailable': False,
        'related_sections': ['111'],
        'victim_context': 'Victim of terrorist act',
        'perpetrator_context': 'Terrorist',
        'note': 'New provision, mirrors UAPA definition'
    },
    
    # Common sections
    '3(5)': {
        'crime': 'All',
        'title': 'Acts done by several persons in furtherance of common intention',
        'description': 'When criminal act is done by several persons in furtherance of common intention of all, each of such persons is liable for that act as if done by him alone',
        'severity': 'medium',
        'punishment': {
            'min': 'As per main offence',
            'max': 'As per main offence',
            'fine': 'As applicable'
        },
        'legal_elements': ['Criminal act by several persons', 'Common intention', 'Each liable as if done by him alone'],
        'keywords': ['common intention', 'joint liability', 'group crime', 'shared intention', 'joint criminal enterprise'],
        'cognizable': 'Depends on main offence',
        'bailable': 'Depends on main offence',
        'related_sections': ['61'],
        'victim_context': 'Victim of act by multiple persons',
        'perpetrator_context': 'Person acting with others in furtherance of common intention'
    },
    
    '61(1)': {
        'crime': 'All',
        'title': 'Criminal conspiracy definition',
        'description': 'When two or more persons agree to do or cause to be done illegal act or act by illegal means, such agreement is criminal conspiracy',
        'severity': 'medium',
        'punishment': {
            'min': 'As per conspiracy provisions',
            'max': 'As per conspiracy provisions',
            'fine': 'As applicable'
        },
        'legal_elements': ['Two or more persons', 'Agreement', 'To do illegal act or act by illegal means'],
        'keywords': ['conspiracy', 'criminal agreement', 'joint planning', 'agreement to commit crime', 'plotting'],
        'cognizable': True,
        'bailable': True,
        'related_sections': ['61(2)', '3(5)'],
        'victim_context': 'Intended victim of conspiracy',
        'perpetrator_context': 'Person who enters into criminal conspiracy'
    },
    
    '61(2)': {
        'crime': 'All',
        'title': 'Punishment for criminal conspiracy',
        'description': 'Punishment for criminal conspiracy to commit offence punishable with death, life imprisonment or rigorous imprisonment for 2 years or more',
        'severity': 'medium',
        'punishment': {
            'min': 'As if abetted such offence',
            'max': 'As if abetted such offence',
            'fine': 'As applicable'
        },
        'legal_elements': ['Criminal conspiracy', 'To commit serious offence', 'Punishable as abetment'],
        'keywords': ['conspiracy punishment', 'planning crime', 'agreement to commit serious offence'],
        'cognizable': True,
        'bailable': True,
        'related_sections': ['61(1)', '45'],
        'victim_context': 'Victim of conspired crime',
        'perpetrator_context': 'Conspirator'
    },
    
    '45': {
        'crime': 'All',
        'title': 'Abetment of a thing',
        'description': 'Abetment of thing by instigating person, engaging in conspiracy, or intentionally aiding by act or illegal omission',
        'severity': 'medium',
        'punishment': {
            'min': 'Varies by offence abetted',
            'max': 'Varies by offence abetted',
            'fine': 'As applicable'
        },
        'legal_elements': ['Instigation', 'Or conspiracy', 'Or intentional aid', 'Of an offence'],
        'keywords': ['abetment', 'instigation', 'aiding', 'encouraging crime', 'facilitating offence'],
        'cognizable': 'Depends on offence abetted',
        'bailable': 'Depends on offence abetted',
        'related_sections': ['49', '61'],
        'victim_context': 'Victim of abetted crime',
        'perpetrator_context': 'Abettor'
    },
    
    '49': {
        'crime': 'All',
        'title': 'Punishment of abetment if act abetted is committed',
        'description': 'Whoever abets offence shall if act abetted is committed be punished with punishment provided for offence',
        'severity': 'medium',
        'punishment': {
            'min': 'Same as main offence',
            'max': 'Same as main offence',
            'fine': 'As applicable'
        },
        'legal_elements': ['Abetment', 'Act abetted actually committed', 'Punishment same as main offender'],
        'keywords': ['abetment punishment', 'facilitator punishment', 'aiding completed crime'],
        'cognizable': 'Depends on offence',
        'bailable': 'Depends on offence',
        'related_sections': ['45', '61'],
        'victim_context': 'Victim of abetted completed crime',
        'perpetrator_context': 'Abettor of completed crime'
    },
}
