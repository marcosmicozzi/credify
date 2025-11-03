import streamlit as st

st.set_page_config(
    page_title="Privacy Policy - Credify",
    page_icon="🔒",
    layout="wide"
)

st.title("Privacy Policy")
st.markdown("**Last Updated: January 27, 2025**")

st.markdown("""
### Introduction

Credify ("we", "our", or "us") is committed to protecting your privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our application.

### Information We Collect

#### Personal Information
- **Email Address**: Collected during authentication via Google OAuth
- **Display Name**: Optional name you provide for your profile
- **Bio**: Optional biographical information you choose to share
- **Profile Picture**: Optional profile image URL you provide

#### Project and Credit Information
- **YouTube Projects**: Links and metadata for YouTube videos where you claim credits
- **Roles**: Professional roles you claim on projects (e.g., Director, Editor, Producer)
- **Metrics**: Aggregated view counts, likes, comments, and engagement metrics

#### Usage Data
- Authentication and session information
- Interactions with the application (following users, claiming credits, etc.)

### How We Use Your Information

We use the information we collect to:
- Provide and maintain our service
- Authenticate your identity and manage your account
- Aggregate and display your credited projects and metrics
- Enable social features such as following other creators
- Send you important updates about the service
- Comply with legal obligations

### How We Share Your Information

We do not sell your personal information. We may share information in the following circumstances:

- **Public Profile Information**: Your display name, bio, profile picture, and credited projects are visible to other users of the application
- **Service Providers**: We use Supabase for data storage and Google for authentication
- **Legal Requirements**: When required by law or to protect our rights

### Data Storage

Your data is stored securely using Supabase, which employs industry-standard security measures including encryption at rest and in transit.

### Your Rights

You have the right to:
- Access the personal information we hold about you
- Update or correct your information through the Settings page
- Delete your account (contact us for account deletion)
- Opt-out of certain data processing activities

### Third-Party Services

Our application integrates with:
- **Google OAuth**: For user authentication
- **YouTube Data API**: For fetching video metadata and metrics
- **Supabase**: For database and authentication services

These services have their own privacy policies. We encourage you to read them.

### Data Retention

We retain your information for as long as your account is active or as needed to provide services. You may request deletion of your account and associated data at any time.

### Children's Privacy

Our service is not intended for users under the age of 13. We do not knowingly collect information from children under 13.

### Changes to This Privacy Policy

We may update this Privacy Policy from time to time. We will notify you of any changes by posting the new Privacy Policy on this page and updating the "Last Updated" date.

### Contact Us

If you have questions about this Privacy Policy, please contact us at:
- Email: privacy@credify.app

### Compliance

We are committed to compliance with:
- General Data Protection Regulation (GDPR)
- California Consumer Privacy Act (CCPA)
- Other applicable privacy laws and regulations
""")

st.markdown("---")
st.markdown("Back to [Credify Home](/)")
