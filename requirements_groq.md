# Project Overview
The Sample Project is a web platform designed for Sample Client in the General domain. The platform aims to provide customers with a secure and fast way to view their loan status and allow admins to review, approve, or reject loan applications.

# Scope
The scope of the project includes the following functional requirements:
- Customer Loan Status View (FR-01)
- Admin Loan Application Review (FR-02)
- Email Notification on Loan Status Change (FR-03)
The project also includes non-functional requirements for performance, security, and usability.

# Functional Requirements
The following are the functional requirements of the project:
### FR-01: Customer Loan Status View
* Description: Customers can log in and view their loan status.
* Priority: High
* Actors: Customer
* Preconditions: Customer is logged in
* Postconditions: Customer can view their loan status
* Acceptance Criteria:
  - Loan status is displayed correctly
  - Customer can view their loan status after logging in

### FR-02: Admin Loan Application Review
* Description: Admins can review, approve, or reject loan applications.
* Priority: High
* Actors: Admin
* Preconditions: 
  - Admin is logged in
  - Loan application is submitted
* Postconditions: Loan application is reviewed, approved, or rejected
* Acceptance Criteria:
  - Admin can review loan application
  - Admin can approve or reject loan application

### FR-03: Email Notification on Loan Status Change
* Description: Customers receive an email notification when their loan status changes.
* Priority: Medium
* Actors: Customer
* Preconditions: Customer's loan status has changed
* Postconditions: Customer receives an email notification
* Acceptance Criteria:
  - Email notification is sent to customer
  - Email notification contains correct loan status information

# Non-Functional Requirements
The following are the non-functional requirements of the project:
### NFR-01: Performance
* Description: The web platform should be very fast.
* Category: Performance
* Priority: High

### NFR-02: Security
* Description: The web platform should be secure.
* Category: Security
* Priority: High

### NFR-03: Usability
* Description: The web platform should work on mobile devices.
* Category: Usability
* Priority: Low

# Constraints & Assumptions
The following are the constraints and assumptions of the project:
### Constraints
* CON-01: Mobile version can be delayed if it affects the launch timeline (Type: Schedule)

### Assumptions
* ASM-01: The web platform will use an existing email service to send notifications.
* ASM-02: The loan status and application data will be stored in a database.
* ASM-03: The web platform will have a user authentication system.

# Open Points & Clarification Questions
The following are open points and clarification questions that need to be addressed:
1. Q-01: Can you please define what 'very fast' means in terms of specific performance metrics or benchmarks for the web platform? (Priority: Medium)
2. Q-02: What specific aspects of security are being referred to when stating that the web platform should be 'secure', and are there any particular security standards or regulations that need to be met? (Priority: High)
3. Q-03: What information is included in the loan status view that customers can access after logging in? (Priority: Medium)
4. Q-04: What are the criteria for approving or rejecting a loan application, and are there any specific requirements or guidelines that admins should follow during the review process? (Priority: High)
5. Q-05: When should the email notification be sent to customers after their loan status changes, and are there any specific timing requirements or constraints that need to be considered? (Priority: Low)
6. Q-06: Is it a requirement for the web platform to have a user registration and password management system, and if so, what are the specific requirements for these features? (Priority: Medium)