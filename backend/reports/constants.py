from django.db import models


class Category(models.TextChoices):
    BRIBERY = "bribery", "Bribery or extortion"
    MISUSE_OF_FUNDS = "misuse_of_funds", "Misuse of public funds"
    PUBLIC_SERVICE = "public_service", "Public service failure"
    EDUCATION = "education", "Education"
    HEALTHCARE = "healthcare", "Healthcare"
    LAND = "land", "Land and property"
    POLICE = "police", "Police misconduct"
    OTHER = "other", "Other"


class Status(models.TextChoices):
    PENDING = "pending", "Pending review"
    VERIFIED = "verified", "Verified"
    REJECTED = "rejected", "Rejected"


class Decision(models.TextChoices):
    VERIFY = "verify", "Verify"
    REJECT = "reject", "Reject"


# The 64 districts of Bangladesh, used to validate the "district" field.
DISTRICTS = sorted([
    "Bagerhat", "Bandarban", "Barguna", "Barishal", "Bhola", "Bogura",
    "Brahmanbaria", "Chandpur", "Chapai Nawabganj", "Chattogram", "Chuadanga",
    "Cox's Bazar", "Cumilla", "Dhaka", "Dinajpur", "Faridpur", "Feni",
    "Gaibandha", "Gazipur", "Gopalganj", "Habiganj", "Jamalpur", "Jashore",
    "Jhalokathi", "Jhenaidah", "Joypurhat", "Khagrachhari", "Khulna",
    "Kishoreganj", "Kurigram", "Kushtia", "Lakshmipur", "Lalmonirhat",
    "Madaripur", "Magura", "Manikganj", "Meherpur", "Moulvibazar",
    "Munshiganj", "Mymensingh", "Naogaon", "Narail", "Narayanganj",
    "Narsingdi", "Natore", "Netrokona", "Nilphamari", "Noakhali", "Pabna",
    "Panchagarh", "Patuakhali", "Pirojpur", "Rajbari", "Rajshahi",
    "Rangamati", "Rangpur", "Satkhira", "Shariatpur", "Sherpur", "Sirajganj",
    "Sunamganj", "Sylhet", "Tangail", "Thakurgaon",
])
assert len(DISTRICTS) == 64
