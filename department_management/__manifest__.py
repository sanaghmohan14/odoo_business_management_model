{
    'name': 'Department Management',
    'version': '19.0.1.1.1',
    'author': "Benjali",
    'sequence': -10,
    'summary': "Department Management",
    'application': True,
    'installable': True,
    'auto_install': True,
    'depends': ['base', 'crm', "mail", "contacts", 'account','mrp','hr','project','sale'],
    'data': [

        "views/crm_lead.xml"


    ]
}