# PRODUCT REQUIREMENTS DOCUMENT (PRD)
## Mechora – Phase 2: AI-Powered Visual Quality Inspection

**Project:** Mechora  
**Module:** AI Visual Quality Inspection  
**Version:** 1.0  
**Status:** Development Specification  
**Platform:** Web Application  
**Backend:** Django + Django REST Framework  
**Frontend:** HTML, CSS, JavaScript, Bootstrap  
**Database:** PostgreSQL  
**Background Processing:** Celery + Redis  
**AI Framework:** Python + NumPy + Pillow  
**Deployment Context:** Existing Mechora Phase 1 project

---

# 1. Product Overview

## 1.1 Introduction

Mechora Phase 2 introduces an AI-powered visual quality inspection system designed to identify defects in manufactured metal plates.

The system allows engineers to upload images of manufactured products and receive automated inspection results using a pretrained AI classification model supplied by the hackathon organizers.

The application will classify uploaded images into two categories:

- Normal
- Defective

The platform will also provide product management, asynchronous batch inspection, inspection history, supervisor reviews and model performance evaluation.

The existing Mechora Phase 1 application will be extended to support these functionalities.

## 1.2 Problem Statement

Traditional manufacturing quality inspection often requires manual examination of products.

Manual inspection can be time-consuming and may lead to inconsistent decisions between inspectors.

Mechora aims to improve this process by introducing an AI-assisted inspection workflow that:

- Automates initial product classification.
- Provides consistent AI-generated inspection results.
- Maintains inspection records.
- Enables human verification of AI predictions.
- Supports traceability and accountability.
- Provides measurable model performance statistics.

## 1.3 Product Objectives

The primary objectives are:

1. Integrate the pretrained classifier supplied by the organizers.
2. Allow engineers to submit individual or multiple product images.
3. Validate uploaded images before AI inference.
4. Process inspection requests asynchronously.
5. Store inspection results permanently.
6. Provide role-based access control.
7. Allow supervisors to verify or correct AI predictions.
8. Provide inspection history and filtering.
9. Evaluate the supplied model using all 60 labelled sample images.
10. Demonstrate a complete working inspection workflow.

---

# 2. Existing System and Integration Strategy

Mechora already has a working Phase 1 Django application.

Phase 2 must extend the existing application instead of creating a separate Django project.

## 2.1 Existing Components to Reuse

The following components must be reused wherever applicable:

- Existing authentication system.
- Existing user model.
- Existing three user roles.
- Existing login and logout functionality.
- Existing database configuration.
- Existing API infrastructure.
- Existing frontend layout and design system.
- Existing Django project configuration.

No duplicate authentication system or duplicate user-role implementation should be introduced.

## 2.2 New Django Applications

Create two new Django applications:

### Products

Responsible for managing products that can be inspected.

### Inspections

Responsible for image uploads, validation, AI inference, batch processing, inspection records, reviews and evaluation.

## 2.3 Suggested Project Structure

```text
mechora/
│
├── accounts/                  # Existing authentication
├── assistant/                 # Existing assistant
├── dashboard/                 # Existing dashboard
├── machines/                  # Existing machinery
├── manuals/                   # Existing manuals
├── rag/                       # Existing RAG system
│
├── products/                  # New product management
│   ├── models.py
│   ├── views.py
│   ├── serializers.py
│   ├── urls.py
│   └── admin.py
│
├── inspections/               # New inspection module
│   ├── models.py
│   ├── views.py
│   ├── serializers.py
│   ├── permissions.py
│   ├── tasks.py
│   ├── urls.py
│   ├── admin.py
│   │
│   ├── services/
│   │   ├── inference.py
│   │   ├── validation.py
│   │   └── evaluation.py
│   │
│   └── tests/
│
├── round2_resources/
│   ├── Model/
│   ├── Samples/
│   ├── Validation/
│   ├── product_details.csv
│   └── SHA256SUMS.txt
│
├── media/
├── templates/
├── static/
├── mechora/
├── manage.py
└── requirements.txt
```

This structure is a recommendation. Existing project conventions should be preserved where practical.

---

# 3. User Roles and Permissions

The application must support three distinct roles.

All three roles must reuse the existing Phase 1 user accounts and role assignments.

## 3.1 Administrator

**Primary responsibility:** Product management.

Permissions:

- Access product management.
- Create products.
- Edit product information.
- Activate or deactivate products.
- View the product list.
- Access product-related administrative functionality.

The administrator must not be able to modify original AI inspection results.

## 3.2 Engineer

**Primary responsibility:** Perform AI-powered inspections.

Permissions:

- Access the inspection dashboard.
- View available products.
- Upload individual images.
- Upload batches containing up to 10 images.
- View their own inspection records.
- View AI predictions and confidence.
- View processing statuses.
- Filter their inspection history.
- View failure reasons for their own failed submissions.

Restrictions:

- Cannot access other engineers' private inspection histories.
- Cannot review or correct inspection predictions.
- Cannot access supervisor-only APIs.
- Cannot modify saved AI results.

## 3.3 Supervisor

**Primary responsibility:** Review and verify AI inspection results.

Permissions:

- View all inspection records.
- View results submitted by every engineer.
- View uploaded inspection images.
- Review completed AI predictions.
- Confirm the AI prediction.
- Correct an incorrect AI prediction.
- Add optional review comments.
- View original AI results and reviewed results separately.
- View review history and reviewer information.

Restrictions:

- Cannot modify the original AI-generated prediction.
- Cannot change model weights or inference configuration.

## 3.4 Permission Matrix

| Functionality | Administrator | Engineer | Supervisor |
|---|---|---|---|
| Manage products | Yes | No | No |
| Upload images | No | Yes | No |
| Run AI inspection | No | Yes | No |
| View own inspections | No | Yes | Yes |
| View all inspections | No | No | Yes |
| View AI results | No | Yes | Yes |
| Confirm predictions | No | No | Yes |
| Correct predictions | No | No | Yes |
| Add review comments | No | No | Yes |
| View review history | No | No | Yes |

Permissions must be enforced on the backend, not merely by hiding frontend buttons.

An Engineer must receive HTTP 403 Forbidden when attempting to call a supervisor-only review endpoint directly.

---

# 4. Product Management Module

## 4.1 Overview

The product management module allows administrators to manage products available for inspection.

## 4.2 Initial Product

The initial product supplied by the organizers:

- Product ID: P-PLATE01
- Product Name: Demonstration metal plate

Product details must be derived from the supplied product_details.csv.

## 4.3 Product Fields

Suggested product database fields:

| Field | Description |
|---|---|
| id | Unique database identifier |
| product_code | Unique product code |
| name | Product name |
| description | Product description |
| is_active | Product availability |
| created_at | Creation timestamp |
| updated_at | Last modification timestamp |

Additional fields may be included if supported by the supplied product information.

## 4.4 Product Features

- Create new products.
- Edit product information.
- Activate or deactivate products.
- Display all products.
- Prevent duplicate product codes.
- Prevent inspection submissions against inactive products.

The initial demonstration product must be available when the application is deployed.

---

# 5. AI Model Integration

## 5.1 Overview

The organizers have supplied a pretrained binary classification model.

Students are not required to train a new model.

The application must integrate the supplied inference implementation without changing its underlying logic.

## 5.2 Supplied Model Structure

```text
round2_resources/
└── Model/
    ├── classifier/
    │   ├── coef.npy
    │   ├── intercept.npy
    │   ├── mean.npy
    │   └── scale.npy
    │
    ├── classifier.npz
    ├── inference.py
    ├── model_metadata.json
    └── requirements.txt
```

## 5.3 Model Specifications

| Specification | Value |
|---|---|
| Model name | BIT-PLATE-CV-1.0 |
| Product | P-PLATE01 |
| Model type | Binary classification |
| Input | Metal plate image |
| Class 0 | Normal |
| Class 1 | Defective |
| Decision threshold | 0.5 |
| Execution | CPU |
| External API | Not required |
| GPU | Not required |

## 5.4 Inference Process

The application must use the supplied inference.py helper.

Expected processing flow:

1. Receive the uploaded image.
2. Pass the saved image path to the supplied inference function.
3. Load the pretrained model weights.
4. Apply the supplied image preprocessing.
5. Extract the required image features.
6. Generate the prediction.
7. Return the model output.
8. Save the result in the database.

The supplied preprocessing includes:

- EXIF orientation correction.
- RGB conversion.
- Resizing to 128 × 128 pixels.
- Grayscale conversion.
- Cropping the specified image region.
- Feature extraction.
- Feature standardization.
- Classification using the saved weights.
- Probability calculation using sigmoid.

The implementation must follow the supplied helper exactly.

## 5.5 Prediction Output

The application must capture:

- predicted_class
- confidence
- defect_probability
- model_version

The decision rule must remain:

```python
if defect_probability >= 0.5:
    predicted_class = "Defective"
else:
    predicted_class = "Normal"
```

The actual supplied inference function's output format must be inspected before implementing the adapter.

## 5.6 Confidence Display

The confidence value represents the probability assigned to the predicted class.

Example:

```text
Prediction: Defective
Confidence: 94%
Defect Probability: 94%
Model Version: BIT-PLATE-CV-1.0
```

These values are illustrative.

The interface must not describe confidence as a verified safety probability or guaranteed real-world accuracy.

## 5.7 Model Integrity

The following must not be modified:

- classifier.npz
- Saved model weights.
- Feature extraction logic.
- Preprocessing logic.
- Classification threshold.

The application must preserve the supplied model files and their checksums.

---

# 6. Image Upload and Validation Module

## 6.1 Overview

Engineers must be able to upload product images for AI inspection.

The application must support individual uploads and batch uploads.

## 6.2 Supported Formats

Only:

- JPEG
- PNG

Other file types must be rejected.

Validation must inspect actual file content rather than trusting the filename or extension.

## 6.3 File Restrictions

| Validation | Requirement |
|---|---|
| Supported formats | JPEG and PNG |
| Maximum file size | 5 MiB per image |
| Minimum width | 64 pixels |
| Minimum height | 64 pixels |
| Maximum width | 4096 pixels |
| Maximum height | 4096 pixels |
| Maximum batch size | 10 images |
| Minimum batch size | 1 image |

## 6.4 Validation Process

For every uploaded file:

1. Check whether a file was submitted.
2. Check the actual file format.
3. Verify that the image can be decoded.
4. Check file size.
5. Check image dimensions.
6. Reject invalid files.
7. Send only valid images to the inference system.

Invalid files must never reach the AI model.

## 6.5 Validation Error Messages

The application should provide readable error messages.

Examples:

- Unsupported file format.
- Uploaded file exceeds the 5 MiB limit.
- Image dimensions are below the minimum requirement.
- Image dimensions exceed the maximum requirement.
- The uploaded file is not a valid image.
- The image file is corrupted.

---

# 7. Batch Inspection and Background Processing

## 7.1 Overview

The application must support batch inspection of multiple images.

AI inference should run in the background to prevent long-running requests from blocking the user interface.

## 7.2 Technologies

- Celery: Background task execution.
- Redis: Message broker and task queue.

## 7.3 Batch Requirements

- Accept between 1 and 10 images.
- Create an individual inspection record for each submitted image.
- Validate every image independently.
- Queue valid images for inference.
- Save invalid submissions as failed attempts.
- Process valid images even if other images in the same batch are invalid.

## 7.4 Inspection Status

Every inspection item must have one of the following statuses:

| Status | Meaning |
|---|---|
| Queued | Waiting for processing |
| Processing | Currently running inference |
| Completed | AI prediction successfully generated |
| Failed | Validation or inference failed |

## 7.5 Failure Handling

Each failed item must store a readable failure reason.

Example:

```text
Batch ID: BATCH-001

Image 1: Completed
Image 2: Failed - Invalid image format
Image 3: Completed
Image 4: Failed - Image dimensions too small
Image 5: Completed
```

Failure of one item must not interrupt the remaining valid items.

Invalid images must not receive fabricated AI predictions.

## 7.6 Batch Tracking

The interface must display:

- Total submitted images.
- Completed count.
- Failed count.
- Queued count.
- Processing count.

The engineer must be able to refresh the page and retrieve the current status from the backend.

---

# 8. Inspection Management Module

## 8.1 Overview

Every image submission must produce an inspection record.

Inspection records must persist in the database across browser refreshes and application restarts.

## 8.2 Inspection Database Fields

Suggested fields:

| Field | Description |
|---|---|
| id | Unique inspection ID |
| batch_id | Associated batch identifier, if applicable |
| product | Associated product |
| image | Stored image reference |
| original_filename | Original uploaded filename |
| submitted_by | Engineer who submitted the image |
| predicted_class | Original AI prediction |
| confidence | Model confidence |
| defect_probability | Probability of defective class |
| model_version | Model version |
| status | Processing status |
| failure_reason | Failure description, if applicable |
| created_at | Submission timestamp |
| completed_at | Completion timestamp |

Fields related to prediction must remain empty when validation fails before inference.

## 8.3 Image Storage

Uploaded images must be stored using Django's configured media storage.

The database must store image references rather than image binary data.

## 8.4 Inspection Identification

Every inspection must have a unique identifier.

Every batch must also have a unique identifier.

## 8.5 Inspection Details

Users must be able to open an inspection record and view:

- Inspection ID.
- Product information.
- Uploaded image.
- Original filename.
- AI prediction.
- Confidence.
- Defect probability.
- Model version.
- Submission timestamp.
- Processing status.
- Failure reason, where applicable.
- Review information, where applicable.

---

# 9. Inspection History Module

## 9.1 Engineer History

Engineers must be able to view their own inspection history.

They must not be able to access another engineer's inspection records.

## 9.2 Supervisor History

Supervisors must be able to view all inspection records.

## 9.3 Filters

The inspection history must support:

- Filter by predicted class.
- Filter by review status.
- Filter by processing status.
- Search by inspection ID.
- Filter by product.
- Filter by date range, where practical.

## 9.4 Review Status

The application should distinguish:

- Pending Review.
- Confirmed.
- Corrected.

Failed inspections and incomplete inspections must not be treated as completed AI predictions awaiting review.

---

# 10. Supervisor Review Module

## 10.1 Overview

AI predictions must be reviewable by supervisors.

The supervisor must be able to confirm or correct completed inspection results.

## 10.2 Review Process

1. Supervisor opens an inspection.
2. Supervisor views the uploaded image.
3. Supervisor views the original AI prediction.
4. Supervisor decides whether the prediction is correct.
5. Supervisor confirms or selects the corrected class.
6. Supervisor optionally adds a comment.
7. The application saves the review.
8. The original AI prediction remains unchanged.

## 10.3 Review Fields

Create a separate review record containing:

| Field | Description |
|---|---|
| id | Review ID |
| inspection | Associated inspection |
| reviewed_class | Supervisor's final classification |
| reviewer | Supervisor user |
| comment | Optional review comment |
| reviewed_at | Review timestamp |

## 10.4 Review Rules

- Only supervisors can submit reviews.
- Only completed inspections can be reviewed.
- A review must be linked to an existing inspection.
- The original prediction must remain immutable.
- The reviewer identity and timestamp must be recorded.
- The review must persist after refresh and restart.

## 10.5 Review Interface

Display:

Original AI Prediction: Defective

Supervisor Decision:

- Confirm AI prediction.
- Correct to Normal.
- Correct to Defective.

Optional review comment:

"Surface condition is acceptable."

The final review must be displayed separately from the original AI prediction.

---

# 11. Database Design

The application must use the existing Mechora database configuration.

Suggested database entities:

## 11.1 Product

Stores product information.

## 11.2 Inspection

Stores each submitted image and its processing and AI prediction results.

## 11.3 InspectionReview

Stores supervisor review information separately.

## 11.4 InspectionBatch

Stores batch-level information, such as batch identifier, submitting user, total items and submission time.

## 11.5 Relationships

```text
User
  |
  | 1
  |
  | Many
  v
Inspection
  |
  | Many
  |
  | 1
  v
Product


InspectionBatch
  |
  | 1
  |
  | Many
  v
Inspection


Inspection
  |
  | 1
  |
  | 0 or 1
  v
InspectionReview

User (Supervisor)
  |
  | 1
  |
  | Many
  v
InspectionReview
```

The existing User model must be referenced using Django's configured user model rather than creating another user table.

---

# 12. Frontend Requirements

The Phase 2 frontend must follow Mechora's existing design system and navigation structure.

Do not redesign unrelated Phase 1 functionality.

## 12.1 Engineer Dashboard

Display:

- Total inspections.
- Normal predictions.
- Defective predictions.
- Pending inspections.
- Failed inspections.
- Recent inspection activity.

## 12.2 Product Selection

Engineers must be able to select an active product before uploading images.

## 12.3 Image Upload Interface

Provide:

- Single image upload.
- Multiple image upload.
- Drag-and-drop support.
- Image previews.
- File names and file sizes.
- Validation feedback.
- Remove selected image option.
- Batch submission.

Display the supported file requirements clearly.

## 12.4 Inspection Results Page

Display:

- Inspection image.
- Predicted classification.
- Confidence.
- Defect probability.
- Model version.
- Processing status.
- Review status.

Use clear visual distinction between Normal, Defective, Failed and Pending states.

## 12.5 Inspection History Page

Display an organized table with:

- Inspection ID.
- Product.
- Image thumbnail.
- Predicted class.
- Confidence.
- Submission date.
- Processing status.
- Review status.
- View details action.

Provide the required filters.

## 12.6 Supervisor Dashboard

Display:

- Total inspections.
- Inspections awaiting review.
- Confirmed predictions.
- Corrected predictions.
- Recent review activity.

Provide access to all inspection records and review actions.

## 12.7 Administrator Product Management

Display:

- Product list.
- Add product.
- Edit product.
- Product status.
- Product details.

---

# 13. API Requirements

Use Django REST Framework.

The API must enforce authentication, ownership and role permissions.

Suggested endpoints:

## Products

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/products/` | List products |
| POST | `/api/products/` | Create product |
| GET | `/api/products/{id}/` | Retrieve product |
| PATCH | `/api/products/{id}/` | Update product |

Product creation and editing must be restricted to administrators.

## Inspections

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/inspections/` | Submit single image |
| POST | `/api/inspections/batch/` | Submit batch |
| GET | `/api/inspections/` | List permitted inspections |
| GET | `/api/inspections/{id}/` | Inspection details |
| GET | `/api/inspections/{id}/status/` | Processing status |
| GET | `/api/inspections/statistics/` | Dashboard statistics |

Engineer list queries must return only that engineer's records.

Supervisor queries may return all inspection records.

## Reviews

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/inspections/{id}/review/` | Submit supervisor review |
| GET | `/api/inspections/{id}/review/` | Retrieve review |

Review creation must be supervisor-only.

An Engineer calling the review endpoint must receive HTTP 403.

## Batch Status

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/batches/{id}/` | Retrieve batch summary |
| GET | `/api/batches/{id}/items/` | Retrieve batch item statuses |

Exact URL design may be adjusted to match existing Mechora API conventions.

---

# 14. Model Evaluation Module

## 14.1 Overview

The application must evaluate the pretrained classifier using the supplied 60 labelled sample images.

The evaluation process must not train or modify the model.

## 14.2 Dataset

Location:

```text
round2_resources/
└── Samples/
    ├── images/
    └── labels.csv
```

Dataset composition:

- 30 Normal images.
- 30 Defective images.
- 60 total images.

## 14.3 Evaluation Process

1. Read the sample image paths from labels.csv.
2. Load each image.
3. Pass the image to the supplied inference helper.
4. Record the predicted class.
5. Read the actual class from labels.csv.
6. Compare actual and predicted classifications.
7. Calculate evaluation metrics.

The labels must only be used for evaluation, never as inference inputs.

## 14.4 Confusion Matrix

Use the following format:

| Actual / Predicted | Normal | Defective |
|---|---:|---:|
| Normal | TN | FP |
| Defective | FN | TP |

Definitions:

- TP: Defective image correctly predicted as Defective.
- TN: Normal image correctly predicted as Normal.
- FP: Normal image incorrectly predicted as Defective.
- FN: Defective image incorrectly predicted as Normal.

## 14.5 Defect Recall

Defect recall is the percentage of actual defective images correctly identified.

Formula:

Defect Recall = TP / (TP + FN)

Report the result as a percentage.

## 14.6 Additional Metrics

The evaluation report should include:

- Total samples.
- Successfully processed samples.
- Failed predictions.
- True Positives.
- True Negatives.
- False Positives.
- False Negatives.
- Accuracy.
- Precision.
- Defect Recall.
- F1 Score.

Failed or missing predictions must be reported and must not be silently excluded from the evaluation.

## 14.7 Limitations

The evaluation report must clearly state:

- The dataset contains synthetic images.
- The dataset contains only 60 samples.
- The model is trained for a specific product and fixed image framing.
- Results do not establish real-world industrial reliability.
- Unfamiliar defects and different image conditions may not be recognized reliably.

---

# 15. Security Requirements

Security must be implemented on the backend.

Requirements:

1. All inspection APIs require authentication.
2. Engineers can only access their own inspection records.
3. Supervisors can access all inspection records.
4. Only administrators can manage products.
5. Only supervisors can review inspections.
6. Uploaded files must be validated before inference.
7. File size restrictions must be enforced server-side.
8. File content must be verified.
9. Image paths must be handled safely.
10. The original AI prediction must not be editable through ordinary user APIs.
11. Review records must contain reviewer identity and timestamps.
12. Sensitive configuration must use environment variables.
13. Uploaded files must not be treated as trusted executable content.

---

# 16. Performance and Reliability Requirements

- Image inference must execute in the background for batch submissions.
- The web server must not wait for an entire batch to finish.
- Each image must have an independent processing result.
- A failed image must not stop other valid images.
- Processing status must persist in the database.
- The application must recover sensibly from worker failures.
- Repeated status requests must not trigger duplicate inference.
- Database operations must maintain consistent inspection states.
- Uploaded images must be stored reliably.

Celery task retries should be implemented carefully to avoid duplicate predictions and duplicate inspection records.

---

# 17. Testing Requirements

The following automated tests are mandatory.

## 17.1 Image Validation Tests

- Valid JPEG accepted.
- Valid PNG accepted.
- Unsupported file rejected.
- Fake JPEG rejected.
- Corrupted image rejected.
- Image smaller than 64 × 64 rejected.
- Image larger than 4096 × 4096 rejected.
- File larger than 5 MiB rejected.
- Empty batch rejected.
- Batch containing more than 10 files rejected.

## 17.2 Permission Tests

- Engineer can submit an inspection.
- Engineer can view their own history.
- Engineer cannot access another engineer's private records.
- Engineer cannot create supervisor reviews.
- Direct review API request from Engineer returns HTTP 403.
- Supervisor can view all inspections.
- Supervisor can submit reviews.
- Administrator can manage products.

## 17.3 Persistence Tests

- Inspection records persist after retrieval.
- Prediction information is saved.
- Failed attempts are saved.
- Batch statuses are saved.
- Supervisor reviews persist.
- Original AI predictions remain unchanged after review.

## 17.4 AI Integration Tests

- Supplied inference helper loads successfully.
- Valid sample image produces an output.
- Model version is captured.
- Decision threshold remains 0.5.
- Supplied model files remain unchanged.

---

# 18. Demonstration Requirements

The final application must support the following demonstration sequence.

### Demonstration 1: Administrator

- Log in as Administrator.
- Open product management.
- Display P-PLATE01.
- Add or edit a product.

### Demonstration 2: Engineer

- Log in as Engineer.
- Open inspection dashboard.
- Select the product.
- Upload one valid image.
- Display AI prediction and confidence.
- Open inspection history.

### Demonstration 3: Batch Processing

- Upload multiple valid and invalid images.
- Show processing statuses.
- Show completed results.
- Show failed image reasons.
- Demonstrate that valid files continue processing.

### Demonstration 4: Supervisor Review

- Log in as Supervisor.
- View all inspections.
- Open an inspection.
- Confirm or correct the prediction.
- Add a review comment.
- Refresh the page.
- Demonstrate that the original AI result and supervisor decision are both preserved.

### Demonstration 5: Permission Enforcement

- Log in as Engineer.
- Attempt to submit a review using the API directly.
- Demonstrate the HTTP 403 Forbidden response.

### Demonstration 6: Model Evaluation

- Display the confusion matrix.
- Explain TP, TN, FP and FN.
- Display defect recall.
- Explain the limitations of the synthetic dataset.

---

# 19. Out of Scope

The following functionality is not required for this challenge:

- Training a new AI model.
- Modifying the pretrained classifier.
- Developing a new neural network.
- Object detection or bounding boxes.
- Real-time camera inspection.
- GPU-based inference.
- External paid AI APIs.
- Multi-product defect classification beyond the supplied model's scope.
- Automated machine control.
- Automatic production-line rejection.

The system must focus on the supplied binary classifier and the specified demonstration metal plate.

---

# 20. Acceptance Criteria

The project is considered complete when all the following conditions are satisfied.

| ID | Acceptance criterion |
|---|---|
| AC-01 | Existing Phase 1 authentication works without duplication. |
| AC-02 | Existing three roles are reused correctly. |
| AC-03 | Administrator can manage products. |
| AC-04 | Engineer can upload individual images. |
| AC-05 | Engineer can upload batches of 1–10 images. |
| AC-06 | Invalid images are rejected before inference. |
| AC-07 | Supplied pretrained classifier produces predictions. |
| AC-08 | Model threshold and preprocessing remain unchanged. |
| AC-09 | Valid batch items process independently. |
| AC-10 | Processing statuses are persisted. |
| AC-11 | Inspection records survive application restart. |
| AC-12 | Engineers can only access their own inspection history. |
| AC-13 | Supervisors can access all inspections. |
| AC-14 | Supervisors can confirm or correct predictions. |
| AC-15 | Original AI predictions remain unchanged. |
| AC-16 | Engineer review API requests are rejected. |
| AC-17 | Evaluation uses all 60 labelled sample images. |
| AC-18 | Confusion matrix and defect recall are reported. |
| AC-19 | Automated validation, permission and persistence tests pass. |
| AC-20 | Complete demonstration workflow is operational. |

---

# 21. Development Priorities

Development must follow this order to reduce integration problems.

**Priority 1 – Foundation**
- Inspect existing authentication and user roles.
- Create Products and Inspections applications.
- Configure database models.
- Preserve existing Phase 1 functionality.

**Priority 2 – AI Integration**
- Inspect supplied inference.py.
- Install required dependencies.
- Run the model independently.
- Create the Django inference adapter.

**Priority 3 – Backend Functionality**
- Implement image validation.
- Implement inspection APIs.
- Implement role-based permissions.
- Implement persistent inspection records.

**Priority 4 – Background Processing**
- Configure Redis.
- Configure Celery.
- Implement batch processing.
- Implement independent failure handling.

**Priority 5 – Human Review**
- Implement supervisor review APIs.
- Preserve original AI predictions.
- Store review information separately.

**Priority 6 – Frontend**
- Build administrator product management.
- Build engineer inspection dashboard.
- Build upload and results interfaces.
- Build supervisor review interface.

**Priority 7 – Evaluation and Testing**
- Evaluate all 60 samples.
- Generate confusion matrix.
- Calculate defect recall.
- Run automated tests.
- Prepare final demonstration.

---

# 22. Final Product Vision

Mechora Phase 2 will provide a complete AI-assisted visual quality inspection workflow.

The application will connect three important components:

1. **AI:** Automatically classifies manufactured metal plate images.
2. **Software:** Manages uploads, processing, records and permissions.
3. **Human verification:** Allows supervisors to verify and correct AI predictions.

The final system must be reliable, easy to demonstrate, secure and consistent with the supplied challenge requirements.

**Core principle:** The AI generates the initial prediction, the application manages the inspection workflow, and the supervisor provides the human review. Original AI results must always remain traceable.