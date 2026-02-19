# PRD — Loan Portal
> **Persona**: CTO  |  **Version**: v1  |  **Completeness**: 100%

## 1. Project Overview
- **Project**: Loan Portal
- **Client**: FinCorp
- **Domain**: FinTech

## 2. Goals & Success Metrics
- Primary goal: deliver the features described in this PRD.
- Success metric: all acceptance criteria pass UAT.

## 3. Scope
### In-Scope
- User Authentication
- Admin Review Workflow
- Email Notifications
- View Loan Status
### Out-of-Scope
- Any feature not listed above (to be confirmed in follow-up).

## 4. Stakeholders & Personas
- **Admin**
- **Customer**
- **User**

## 5. Functional Requirements
### FR-01: User Authentication
Users can securely log in to access the system.
- **Priority**: High
- **Actors**: User, Customer
- **Acceptance Criteria**:
  - Functionality works as described.
  - Validated in UAT.
  - Error cases are handled gracefully.

### FR-02: Admin Review Workflow
Admins can review, approve, or reject submissions.
- **Priority**: High
- **Actors**: Admin
- **Acceptance Criteria**:
  - Functionality works as described.
  - Validated in UAT.
  - Error cases are handled gracefully.

### FR-03: Email Notifications
The system sends email notifications on status changes.
- **Priority**: Medium
- **Actors**: User, Customer
- **Acceptance Criteria**:
  - Functionality works as described.
  - Validated in UAT.
  - Error cases are handled gracefully.

### FR-04: View Loan Status
Customers can view the current status of their loan.
- **Priority**: High
- **Actors**: Customer
- **Acceptance Criteria**:
  - Functionality works as described.
  - Validated in UAT.
  - Error cases are handled gracefully.

## 6. Non-Functional Requirements
### NFR-01: Performance
- **Category**: Performance
- **Priority**: High
The system must respond within acceptable time bounds (targets to be confirmed).

### NFR-02: Security
- **Category**: Security
- **Priority**: High
The system must implement authentication, authorisation, and secure data handling.

### NFR-03: Usability / Responsiveness
- **Category**: Usability
- **Priority**: Medium
The UI must be usable on mobile and desktop devices.

## 7. Constraints & Assumptions
### Constraints
- **CON-01**: Delivery includes a web application.
### Assumptions
- **ASM-01**: Mobile scope (responsive web vs native) TBD.

## 8. Derived Architecture Hints
- **Layers**: Web Frontend (HTML/CSS/JS), Mobile App (iOS/Android or Responsive Web)
- **Integrations**: Email Service (SMTP / SendGrid / SES)

## 9. Open Points & Clarification Questions
- **Q-01 [high]**: Can you define each user role and their exact permissions within the system? _(links: AMB-01, AMB-02)_
- **Q-02 [medium]**: Which events trigger email notifications? What should the email content/template include? _(links: AMB-03)_
- **Q-03 [medium]**: This requirement was inferred from context. Can you confirm it is in scope and provide details? _(links: AMB-04)_

## 10. Identified Gaps
- **AMB-01** [HIGH] (✗ Open): Security NFR present but specifics missing: auth mechanism (OTP/SSO/OAuth), RBAC roles, encryption standard, audit logging.
- **AMB-02** [HIGH] (✗ Open): Multiple actors detected (Admin, Customer, User) but role-based permissions and access boundaries are not defined.
- **AMB-03** [MEDIUM] (✗ Open): Email notifications requested but trigger events, templates, and delivery SLA are not specified.
- **AMB-04** [MEDIUM] (✗ Open): Mobile support is referenced but platform scope (responsive web, iOS, Android) is not decided.

## 11. Version History
- **v1** — Initial version
