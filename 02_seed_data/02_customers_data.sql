-- Insert customers_data into customer table

INSERT INTO customers (name, email, phone) VALUES
    ('Alice Smith',          'alice.smith@gmail.com',       '+250788111001'),
    ('Bob Johnson',          'bob.johnson@gmail.com',       '+250788111002'),
    ('Charlie Brown',        'charlie.brown@gmail.com',     '+250788111003'),
    ('Diana Prince',         'diana.prince@gmail.com',      '+250788111004'),
    ('Ethan Hunt',           'ethan.hunt@gmail.com',        '+250788111005'),
    ('Fatima Al-Sayed',      'fatima.alsayed@gmail.com',    '+250788111006'),
    ('Jean Paul Nkurunziza', 'jeanpaul.nk@gmail.com',       '+250788111007'),
    ('Marie Claire Uwase',   'marieclaire.uwase@gmail.com', '+250788111008'),
    ('David Ochieng',        'david.ochieng@gmail.com',     '+250788111009'),
    ('Grace Mukamana',       'grace.mukamana@gmail.com',    '+250788111010'),
    ('Hassan Abdi',          'hassan.abdi@gmail.com',       '+250788111011'),
    ('Ivy Chen',             'ivy.chen@gmail.com',          '+250788111012'),
    ('Jack O''Connor',       'jack.oconnor@gmail.com',      '+250788111013'),
    ('Keziah Wambui',        'keziah.wambui@gmail.com',     '+250788111014'),
    ('Liam Neeson',          'liam.neeson@gmail.com',       '+250788111015'),
    ('Monica Geller',        'monica.geller@gmail.com',     '+250788111016'),
    ('Nathan Drake',         'nathan.drake@gmail.com',      '+250788111017'),
    ('Olivia Pope',          'olivia.pope@gmail.com',       '+250788111018'),
    ('Peter Parker',         'peter.parker@gmail.com',      '+250788111019'),
    ('Queen Latifah',        'queen.latifah@gmail.com',     '+250788111020');

SELECT * FROM customers ORDER BY customer_id;
