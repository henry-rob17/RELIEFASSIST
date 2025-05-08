
DROP DATABASE IF EXISTS reliefassist_db;
CREATE DATABASE reliefassist_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE reliefassist_db;

CREATE TABLE Disaster (
    disaster_id      INT AUTO_INCREMENT PRIMARY KEY,
    name             VARCHAR(100) NOT NULL,
    location         VARCHAR(150) NOT NULL,
    magnitude        VARCHAR(50),
    start_date       DATE NOT NULL,
    end_date         DATE,
    status           ENUM('Open','Ongoing','Closed') DEFAULT 'Open',
    description      TEXT
);

CREATE TABLE ReliefCenter (
    center_id        INT AUTO_INCREMENT PRIMARY KEY,
    name             VARCHAR(100) NOT NULL,
    address          VARCHAR(200) NOT NULL,
    capacity         INT NOT NULL,
    current_load     INT NOT NULL DEFAULT 0,
    CHECK (current_load <= capacity)
);

CREATE TABLE Resource (
    resource_id      INT AUTO_INCREMENT PRIMARY KEY,
    resource_type    VARCHAR(100) NOT NULL,
    unit             VARCHAR(30) NOT NULL,
    description      TEXT
);

CREATE TABLE CenterResource (
    center_resource_id INT AUTO_INCREMENT PRIMARY KEY,
    center_id          INT NOT NULL,
    resource_id        INT NOT NULL,
    quantity_on_hand   INT NOT NULL DEFAULT 0,
    UNIQUE KEY uk_center_resource (center_id, resource_id),
    CONSTRAINT fk_cr_center   FOREIGN KEY (center_id)  REFERENCES ReliefCenter(center_id),
    CONSTRAINT fk_cr_resource FOREIGN KEY (resource_id) REFERENCES Resource(resource_id)
);

CREATE TABLE Task (
    task_id          INT AUTO_INCREMENT PRIMARY KEY,
    disaster_id      INT NOT NULL,
    center_id        INT,
    description      VARCHAR(255) NOT NULL,
    due_date         DATE,
    status           ENUM('Pending','In-Progress','Complete','Cancelled') DEFAULT 'Pending',
    CONSTRAINT fk_task_disaster FOREIGN KEY (disaster_id) REFERENCES Disaster(disaster_id),
    CONSTRAINT fk_task_center   FOREIGN KEY (center_id)   REFERENCES ReliefCenter(center_id)
);

CREATE TABLE Volunteer (
    volunteer_id     INT AUTO_INCREMENT PRIMARY KEY,
    first_name       VARCHAR(60) NOT NULL,
    last_name        VARCHAR(60) NOT NULL,
    phone            VARCHAR(25),
    email            VARCHAR(120),
    skills           VARCHAR(255)
);

CREATE TABLE TaskAssignment (
    assignment_id    INT AUTO_INCREMENT PRIMARY KEY,
    task_id          INT NOT NULL,
    volunteer_id     INT NOT NULL,
    assigned_date    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    hours_worked     DECIMAL(5,2) DEFAULT 0,
    UNIQUE KEY uk_task_volunteer (task_id, volunteer_id),
    CONSTRAINT fk_ta_task      FOREIGN KEY (task_id)      REFERENCES Task(task_id),
    CONSTRAINT fk_ta_volunteer FOREIGN KEY (volunteer_id) REFERENCES Volunteer(volunteer_id)
);

CREATE TABLE Donor (
    donor_id         INT AUTO_INCREMENT PRIMARY KEY,
    first_name       VARCHAR(60) NOT NULL,
    last_name        VARCHAR(60) NOT NULL,
    phone            VARCHAR(25),
    email            VARCHAR(120)
);

CREATE TABLE Donation (
    donation_id      INT AUTO_INCREMENT PRIMARY KEY,
    donor_id         INT NOT NULL,
    donation_type    ENUM('Cash','In-Kind') NOT NULL,
    amount           DECIMAL(10,2) DEFAULT 0,
    donation_date    DATE NOT NULL,
    notes            TEXT,
    CONSTRAINT fk_donation_donor FOREIGN KEY (donor_id) REFERENCES Donor(donor_id)
);

CREATE TABLE DonationAllocation (
    allocation_id    INT AUTO_INCREMENT PRIMARY KEY,
    donation_id      INT NOT NULL,
    resource_id      INT NOT NULL,
    task_id          INT,
    quantity         INT NOT NULL DEFAULT 0,
    amount_used      DECIMAL(10,2) DEFAULT 0,
    CONSTRAINT fk_da_donation FOREIGN KEY (donation_id) REFERENCES Donation(donation_id),
    CONSTRAINT fk_da_resource FOREIGN KEY (resource_id) REFERENCES Resource(resource_id),
    CONSTRAINT fk_da_task     FOREIGN KEY (task_id)     REFERENCES Task(task_id)
);

CREATE TABLE users (
    user_id   INT AUTO_INCREMENT PRIMARY KEY,
    email     VARCHAR(120) NOT NULL UNIQUE,
    pw_hash   VARCHAR(255) NOT NULL,
    role      ENUM('admin','manager','volunteer','donor','public') NOT NULL DEFAULT 'public'
);

CREATE TABLE Manager (
  manager_id INT AUTO_INCREMENT PRIMARY KEY,
  user_id    INT      NOT NULL,
  office     VARCHAR(100),
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);



INSERT INTO Disaster (name, location, magnitude, start_date, status, description)
VALUES
 ('Hurricane Zara', 'Galveston, TX', 'Category 4', '2025-04-15', 'Ongoing', 'Severe flooding and wind damage'),
 ('Earthquake Delta', 'San Jose, CA', '7.1 Mw', '2025-03-20', 'Closed', 'Aftershocks continue but major rescue ended');

INSERT INTO ReliefCenter (name, address, capacity, current_load)
VALUES
 ('Galveston Island RC', '123 Seawall Blvd, Galveston, TX', 500, 350),
 ('Houston North RC',    '8901 Main St, Houston, TX',       800, 600);

INSERT INTO Resource (resource_type, unit, description)
VALUES
 ('Bottled Water', 'cases', '24x500 mL bottled water'),
 ('First‑Aid Kit', 'kits',  'Standard first‑aid supplies'),
 ('Blanket',       'pcs',   'Thermal disaster blanket');

INSERT INTO CenterResource (center_id, resource_id, quantity_on_hand)
VALUES
 (1, 1, 250),
 (1, 2, 80),
 (2, 1, 400),
 (2, 3, 200);

INSERT INTO Task (disaster_id, center_id, description, due_date, status) VALUES
  (1, 1, 'Distribute water to shelter A', '2025-04-30', 'In-Progress'),
  (1, 1, 'Set up mobile clinic',          '2025-05-02', 'Pending'),
  (2, 2, 'Deliver blankets to families',  '2025-03-22', 'Complete');


INSERT INTO Volunteer (first_name, last_name, phone, email, skills)
VALUES
 ('Alice', 'Nguyen', '555-222-1111', 'alice@example.com', 'Medical, Triage'),
 ('Brian', 'Lopez',  '555-333-2222', 'brian@example.com', 'Logistics'),
 ('Chloe', 'Shah',   '555-444-3333', 'chloe@example.com', 'First Aid');

INSERT INTO TaskAssignment (task_id, volunteer_id, assigned_date, hours_worked)
VALUES
 (1, 2, '2025-04-28', 4.5),
 (1, 3, '2025-04-29', 2.0),
 (3, 1, '2025-03-20', 6.0);

INSERT INTO Donor (first_name, last_name, phone, email)
VALUES
 ('Deepak', 'Patel', '555-777-6666', 'deepak@example.com'),
 ('Elena', 'Garcia', '555-888-7777', 'elena@example.com');

INSERT INTO Donation (donor_id, donation_type, amount, donation_date, notes)
VALUES
 (1, 'Cash', 5000.00, '2025-04-27', 'General relief fund'),
 (2, 'In-Kind', 0, '2025-04-26', '200 cases of bottled water');

INSERT INTO DonationAllocation (donation_id, resource_id, task_id, quantity, amount_used)
VALUES
 (2, 1, 1, 200, 0),
 (1, 2, NULL, 0, 1000.00);
 


-- Quickly check available resources at each center
CREATE VIEW vw_center_stock AS
SELECT rc.center_id, rc.name AS center_name,
       r.resource_type, cr.quantity_on_hand
FROM CenterResource cr
JOIN ReliefCenter rc ON rc.center_id = cr.center_id
JOIN Resource r      ON r.resource_id = cr.resource_id;

-- Summary of donations and usage
CREATE VIEW vw_donation_summary AS
SELECT d.donation_id, CONCAT(do.first_name,' ',do.last_name) AS donor,
       d.donation_type, d.amount,
       IFNULL(SUM(da.amount_used),0) AS amount_spent,
       IFNULL(SUM(da.quantity),0)    AS total_items_allocated
FROM Donation d
JOIN Donor do ON do.donor_id = d.donor_id
LEFT JOIN DonationAllocation da ON da.donation_id = d.donation_id
GROUP BY d.donation_id;


-- 1) Check tasks and assigned volunteers for a given disaster
--    (Change disaster_id as needed)
SELECT t.task_id, t.description, t.status,
       GROUP_CONCAT(CONCAT(v.first_name,' ',v.last_name) SEPARATOR ', ') AS volunteers
FROM Task t
LEFT JOIN TaskAssignment ta ON ta.task_id = t.task_id
LEFT JOIN Volunteer v ON v.volunteer_id = ta.volunteer_id
WHERE t.disaster_id = 1
GROUP BY t.task_id;

-- 2) Resources running low (threshold < 100 units)
SELECT rc.name AS center, r.resource_type, cr.quantity_on_hand
FROM CenterResource cr
JOIN ReliefCenter rc ON rc.center_id = cr.center_id
JOIN Resource r ON r.resource_id = cr.resource_id
WHERE cr.quantity_on_hand < 100;

-- 3) Total donations by donor
SELECT donor, SUM(amount) AS total_cash_contributed
FROM vw_donation_summary
WHERE donation_type = 'Cash'
GROUP BY donor;

