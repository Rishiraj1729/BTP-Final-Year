## 1. Project Overview
- **Project**: Sample Project
- **Client**: Sample Client
- **Domain**: General

## 2. Scope
- **In-scope**: Features explicitly mentioned in the conversation transcript.
- **Out-of-scope**: Anything not stated; to be confirmed during clarification.

## 3. Functional Requirements
### FR-01: User authentication
Users can log in to access the system.
- **Priority**: High
- **Actors**: Customer
- **Acceptance Criteria**:
  - Behavior is implemented as described and validated in UAT.
  - Errors are handled with user-friendly messages.

### FR-02: Admin review workflow
Admins can review, approve, or reject submissions/requests.
- **Priority**: High
- **Actors**: Admin
- **Acceptance Criteria**:
  - Behavior is implemented as described and validated in UAT.
  - Errors are handled with user-friendly messages.

### FR-03: Email notifications
Send email notifications when important status changes occur.
- **Priority**: Medium
- **Actors**: Customer
- **Acceptance Criteria**:
  - Behavior is implemented as described and validated in UAT.
  - Errors are handled with user-friendly messages.

### FR-04: View loan status
Customers can view the current status of their loan/application.
- **Priority**: High
- **Actors**: Customer
- **Acceptance Criteria**:
  - Behavior is implemented as described and validated in UAT.
  - Errors are handled with user-friendly messages.

## 4. Non-Functional Requirements
### NFR-01: Security
- **Category**: Security
- **Priority**: High
The system must follow security best practices (authentication, authorization, secure storage, secure transport).

### NFR-02: Performance
- **Category**: Performance
- **Priority**: High
The system should respond quickly for common user actions (targets to be confirmed).

## 5. Constraints & Assumptions
### Constraints
- **CON-01**: Initial delivery includes a web application.
### Assumptions
- **ASM-01**: Mobile support may be responsive web first; native apps to be confirmed.

## 6. Open Points & Clarification Questions
- **Q-01 [high]**: What are the performance targets (e.g., p95 response time for key screens, expected concurrent users, peak load)? (links: AMB-01)
- **Q-02 [high]**: What authentication method should be used (email/password, OTP, SSO)? What roles exist and what permissions should each role have? (links: AMB-02, AMB-03, AMB-04, AMB-05)
