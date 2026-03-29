#!/usr/bin/env bash
# =============================================================================
# Voter Data Collection API — cURL Examples
# =============================================================================
# Prerequisites:
#   export BASE_URL=http://localhost:8000
#   jq installed for pretty-printing
# =============================================================================

BASE_URL="${BASE_URL:-http://localhost:8000}"
TMP_IMAGE_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_IMAGE_DIR"' EXIT

# Small placeholder files so the multipart upload examples are runnable.
printf 'landmark-image-1' > "$TMP_IMAGE_DIR/landmark1.jpg"
printf 'landmark-image-2' > "$TMP_IMAGE_DIR/landmark2.jpg"
printf 'landmark-image-3' > "$TMP_IMAGE_DIR/landmark3.jpg"

echo "============================================================"
echo " 0. Health Check"
echo "============================================================"
curl -s "$BASE_URL/health" | jq .


# =============================================================================
# 1. AUTH — Login as Super Admin
# =============================================================================
echo ""
echo "============================================================"
echo " 1. Login as Super Admin"
echo "============================================================"
SUPER_TOKEN=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"phone": "9000000000", "password": "SuperSecret@123"}' \
  | jq -r '.access_token')
echo "Super Admin Token: $SUPER_TOKEN"


# =============================================================================
# 2. USERS — Super Admin creates an Admin
# =============================================================================
echo ""
echo "============================================================"
echo " 2. Create Admin user (by Super Admin)"
echo "============================================================"
ADMIN_RESP=$(curl -s -X POST "$BASE_URL/users" \
  -H "Authorization: Bearer $SUPER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "District Admin",
    "phone": "9100000001",
    "password": "AdminPass@123",
    "role": "ADMIN"
  }')
echo "$ADMIN_RESP" | jq .
ADMIN_ID=$(echo "$ADMIN_RESP" | jq -r '.id')


# =============================================================================
# 3. AUTH — Login as Admin
# =============================================================================
echo ""
echo "============================================================"
echo " 3. Login as Admin"
echo "============================================================"
ADMIN_TOKEN=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"phone": "9100000001", "password": "AdminPass@123"}' \
  | jq -r '.access_token')
echo "Admin Token: $ADMIN_TOKEN"


# =============================================================================
# 4. USERS — Admin creates a Field User
# =============================================================================
echo ""
echo "============================================================"
echo " 4. Create Field User (by Admin)"
echo "============================================================"
FIELD_RESP=$(curl -s -X POST "$BASE_URL/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Field Worker One",
    "phone": "9200000002",
    "password": "FieldPass@123",
    "role": "FIELD_USER"
  }')
echo "$FIELD_RESP" | jq .


# =============================================================================
# 5. AUTH — Login as Field User
# =============================================================================
echo ""
echo "============================================================"
echo " 5. Login as Field User"
echo "============================================================"
FIELD_TOKEN=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"phone": "9200000002", "password": "FieldPass@123"}' \
  | jq -r '.access_token')
echo "Field User Token: $FIELD_TOKEN"


# =============================================================================
# 6. USERS — List users (Admin sees their own field users)
# =============================================================================
echo ""
echo "============================================================"
echo " 6. List users visible to Admin"
echo "============================================================"
curl -s "$BASE_URL/users?limit=20&offset=0" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .


# =============================================================================
# 7. USERS — Get my profile
# =============================================================================
echo ""
echo "============================================================"
echo " 7. Get /users/me"
echo "============================================================"
curl -s "$BASE_URL/users/me" \
  -H "Authorization: Bearer $FIELD_TOKEN" | jq .


# =============================================================================
# 8. BUILDINGS — Create a building (apartment block)
# =============================================================================
echo ""
echo "============================================================"
echo " 8. Create Building"
echo "============================================================"
BUILDING_RESP=$(curl -s -X POST "$BASE_URL/buildings" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Sunrise Apartments",
    "address_text": "12 Main Road, Chennai",
    "total_floors": 10
  }')
echo "$BUILDING_RESP" | jq .
BUILDING_ID=$(echo "$BUILDING_RESP" | jq -r '.id')


# =============================================================================
# 9. BUILDINGS — Add a Unit to the building
# =============================================================================
echo ""
echo "============================================================"
echo " 9. Create Unit in Building"
echo "============================================================"
UNIT_RESP=$(curl -s -X POST "$BASE_URL/buildings/units" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"building_id\": \"$BUILDING_ID\",
    \"flat_number\": \"4B\",
    \"floor_number\": 4
  }")
echo "$UNIT_RESP" | jq .
UNIT_ID=$(echo "$UNIT_RESP" | jq -r '.id')


# =============================================================================
# 10. HOUSEHOLDS — Duplicate check before creating
# =============================================================================
echo ""
echo "============================================================"
echo " 10. Duplicate check (should return no duplicates)"
echo "============================================================"
curl -s "$BASE_URL/households/duplicate-check?latitude=13.0827&longitude=80.2707&radius_metres=20" \
  -H "Authorization: Bearer $FIELD_TOKEN" | jq .


# =============================================================================
# 11. HOUSEHOLDS — Create an INDIVIDUAL household
# =============================================================================
echo ""
echo "============================================================"
echo " 11. Create INDIVIDUAL household"
echo "============================================================"
HOUSEHOLD_RESP=$(curl -s -X POST "$BASE_URL/households" \
  -H "Authorization: Bearer $FIELD_TOKEN" \
  -F 'payload={
    "latitude": 13.0827,
    "longitude": 80.2707,
    "address_text": "42 Anna Nagar, Chennai",
    "house_type": "INDIVIDUAL",
    "persons": [
      {"age": 45, "gender": "MALE",   "is_voter": true},
      {"age": 42, "gender": "FEMALE", "is_voter": true},
      {"age": 16, "gender": "MALE",   "is_voter": false}
    ]
  }' \
  -F "landmark_images=@$TMP_IMAGE_DIR/landmark1.jpg;type=image/jpeg" \
  -F "landmark_images=@$TMP_IMAGE_DIR/landmark2.jpg;type=image/jpeg")
echo "$HOUSEHOLD_RESP" | jq .
HOUSEHOLD_ID=$(echo "$HOUSEHOLD_RESP" | jq -r '.id')


# =============================================================================
# 12. HOUSEHOLDS — Create an APARTMENT household (links to Unit)
# =============================================================================
echo ""
echo "============================================================"
echo " 12. Create APARTMENT household (linked to Unit)"
echo "============================================================"
APT_HOUSEHOLD=$(curl -s -X POST "$BASE_URL/households" \
  -H "Authorization: Bearer $FIELD_TOKEN" \
  -F "payload={
    \"latitude\": 13.0900,
    \"longitude\": 80.2800,
    \"address_text\": \"Sunrise Apartments, 12 Main Road, Chennai\",
    \"house_type\": \"APARTMENT\",
    \"unit_id\": \"$UNIT_ID\",
    \"persons\": [
      {\"age\": 38, \"gender\": \"MALE\",   \"is_voter\": true},
      {\"age\": 35, \"gender\": \"FEMALE\", \"is_voter\": true}
    ],
    \"landmark_image_urls\": []
  }" \
  -F "landmark_images=@$TMP_IMAGE_DIR/landmark3.jpg;type=image/jpeg")
echo "$APT_HOUSEHOLD" | jq .
APT_HOUSEHOLD_ID=$(echo "$APT_HOUSEHOLD" | jq -r '.id')


# =============================================================================
# 13. HOUSEHOLDS — Get full details
# =============================================================================
echo ""
echo "============================================================"
echo " 13. Get household details"
echo "============================================================"
curl -s "$BASE_URL/households/$HOUSEHOLD_ID" \
  -H "Authorization: Bearer $FIELD_TOKEN" | jq .


# =============================================================================
# 14. HOUSEHOLDS — Nearby search (PostGIS)
# =============================================================================
echo ""
echo "============================================================"
echo " 14. Nearby households within 1 km"
echo "============================================================"
curl -s "$BASE_URL/households/nearby?latitude=13.0827&longitude=80.2707&radius_metres=1000&limit=10" \
  -H "Authorization: Bearer $FIELD_TOKEN" | jq .


# =============================================================================
# 15. VERIFICATION — Field user marks household as MATCHED
# =============================================================================
echo ""
echo "============================================================"
echo " 15. Submit MATCHED verification"
echo "============================================================"
curl -s -X POST "$BASE_URL/verification" \
  -H "Authorization: Bearer $FIELD_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"household_id\": \"$HOUSEHOLD_ID\",
    \"status\": \"MATCHED\",
    \"notes\": \"All members present, data confirmed accurate.\"
  }" | jq .


# =============================================================================
# 16. VERIFICATION — Field user marks another household as MISMATCH
# =============================================================================
echo ""
echo "============================================================"
echo " 16. Submit MISMATCH verification"
echo "============================================================"
curl -s -X POST "$BASE_URL/verification" \
  -H "Authorization: Bearer $FIELD_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"household_id\": \"$APT_HOUSEHOLD_ID\",
    \"status\": \"MISMATCH\",
    \"notes\": \"One voter not found at the address.\"
  }" | jq .


# =============================================================================
# 17. AUDIT — Verification history for a household
# =============================================================================
echo ""
echo "============================================================"
echo " 17. Verification history (audit trail)"
echo "============================================================"
curl -s "$BASE_URL/households/$HOUSEHOLD_ID/verifications" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .


# =============================================================================
# 18. AUDIT — Collection records for a household
# =============================================================================
echo ""
echo "============================================================"
echo " 18. Collection records (audit trail)"
echo "============================================================"
curl -s "$BASE_URL/households/$HOUSEHOLD_ID/collection-records" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .


# =============================================================================
# 19. BULK UPLOAD — Offline sync of multiple households
# =============================================================================
echo ""
echo "============================================================"
echo " 19. Bulk upload (offline sync) — 2 households"
echo "============================================================"
curl -s -X POST "$BASE_URL/households/bulk" \
  -H "Authorization: Bearer $FIELD_TOKEN" \
  -F 'payload={
    "households": [
      {
        "latitude": 13.1000,
        "longitude": 80.2900,
        "address_text": "10 Velachery Road",
        "house_type": "INDIVIDUAL",
        "persons": [
          {"age": 55, "gender": "FEMALE", "is_voter": true}
        ]
      },
      {
        "latitude": 13.1050,
        "longitude": 80.2950,
        "address_text": "15 Velachery Road",
        "house_type": "INDIVIDUAL",
        "persons": [
          {"age": 30, "gender": "MALE", "is_voter": true},
          {"age": 28, "gender": "FEMALE", "is_voter": true},
          {"age": 5,  "gender": "MALE", "is_voter": false}
        ]
      }
    ]
  }' \
  -F "landmark_images_0=@$TMP_IMAGE_DIR/landmark1.jpg;type=image/jpeg" \
  -F "landmark_images_0=@$TMP_IMAGE_DIR/landmark2.jpg;type=image/jpeg" \
  -F "landmark_images_1=@$TMP_IMAGE_DIR/landmark3.jpg;type=image/jpeg" | jq .


# =============================================================================
# 20. SOFT DELETE — Admin deletes a household
# =============================================================================
echo ""
echo "============================================================"
echo " 20. Soft-delete household"
echo "============================================================"
curl -s -X DELETE "$BASE_URL/households/$APT_HOUSEHOLD_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .


# =============================================================================
# 21. LIST buildings' units
# =============================================================================
echo ""
echo "============================================================"
echo " 21. List units for building"
echo "============================================================"
curl -s "$BASE_URL/buildings/$BUILDING_ID/units" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .

echo ""
echo "============================================================"
echo " All examples complete."
echo "============================================================"
