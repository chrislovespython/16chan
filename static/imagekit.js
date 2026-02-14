/**
 * ImageKit Upload Handler
 * Handles drag & drop, file selection, and upload to ImageKit
 */

// Check if ImageKit is configured (using window object to avoid conflicts)
const imagekitConfigured = typeof window.imagekitAuth !== 'undefined' && window.imagekitAuth !== null;

console.log('[ImageKit] Configured:', imagekitConfigured);

if (imagekitConfigured) {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const preview = document.getElementById('preview');
    const progress = document.getElementById('progress');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    const imageUrlInput = document.getElementById('imageUrl');
    const imageThumbnailInput = document.getElementById('imageThumbnail');

    // Only set up handlers if elements exist
    if (dropZone && fileInput && preview && progress) {
        
        // Click to select file
        dropZone.addEventListener('click', () => {
            fileInput.click();
        });

        // File selected via input
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleFile(e.target.files[0]);
            }
        });

        // Drag & drop handlers
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragging');
        });

        dropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragging');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragging');
            
            if (e.dataTransfer.files.length > 0) {
                handleFile(e.dataTransfer.files[0]);
            }
        });
    }

    function handleFile(file) {
        console.log('[ImageKit] File selected:', file.name, file.type, file.size);
        
        // Validate file type
        if (!file.type.startsWith('image/')) {
            alert('Please select an image file');
            return;
        }
        
        // Validate file size (10MB max)
        if (file.size > 10 * 1024 * 1024) {
            alert('File too large. Maximum size is 10MB');
            return;
        }
        
        // Show preview
        const reader = new FileReader();
        reader.onload = (e) => {
            preview.innerHTML = `<img src="${e.target.result}" alt="Preview">`;
            preview.style.display = 'block';
        };
        reader.readAsDataURL(file);
        
        // Upload to ImageKit
        uploadToImageKit(file);
    }

    function uploadToImageKit(file) {
        console.log('[ImageKit] Starting upload...');
        
        // Show progress
        progress.style.display = 'block';
        progressFill.style.width = '0%';
        progressText.textContent = 'Uploading...';
        
        // Create form data
        const formData = new FormData();
        formData.append('file', file);
        formData.append('publicKey', window.imagekitAuth.publicKey);
        formData.append('signature', window.imagekitAuth.signature);
        formData.append('expire', window.imagekitAuth.expire);
        formData.append('token', window.imagekitAuth.token);
        formData.append('fileName', file.name);
        
        // Upload with XMLHttpRequest for progress tracking
        const xhr = new XMLHttpRequest();
        
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percent = (e.loaded / e.total) * 100;
                progressFill.style.width = percent + '%';
                progressText.textContent = `Uploading... ${Math.round(percent)}%`;
                console.log('[ImageKit] Upload progress:', Math.round(percent) + '%');
            }
        });
        
        xhr.addEventListener('load', () => {
            if (xhr.status === 200) {
                const response = JSON.parse(xhr.responseText);
                console.log('[ImageKit] Upload successful:', response);
                
                // Set image URLs
                imageUrlInput.value = response.url;
                imageThumbnailInput.value = response.thumbnailUrl || response.url;
                
                progressText.textContent = 'Upload complete! ✓';
                progressFill.style.width = '100%';
                progressFill.style.background = '#789922';
                
                // Update preview with uploaded image
                preview.innerHTML = `<img src="${response.thumbnailUrl || response.url}" alt="Uploaded">`;
                
                console.log('[ImageKit] Image URL:', response.url);
            } else {
                console.error('[ImageKit] Upload failed:', xhr.status, xhr.responseText);
                alert('Upload failed: ' + xhr.statusText);
                progress.style.display = 'none';
            }
        });
        
        xhr.addEventListener('error', () => {
            console.error('[ImageKit] Upload error');
            alert('Upload failed. Please try again.');
            progress.style.display = 'none';
        });
        
        xhr.open('POST', 'https://upload.imagekit.io/api/v1/files/upload');
        xhr.send(formData);
    }
} else {
    console.log('[ImageKit] Not configured - image upload disabled');
}

// Bury button handlers (separate from ImageKit)
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.bury-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            const postId = this.dataset.postId;
            console.log('[BURY] Burying post:', postId);
            
            try {
                const response = await fetch('/api/bury/' + postId, {
                    method: 'POST'
                });
                
                const data = await response.json();
                console.log('[BURY] Response:', data);
                
                if (data.success) {
                    this.textContent = '[Bury ' + data.bury_score + ']';
                    this.disabled = true;
                    this.style.opacity = '0.5';
                } else {
                    alert(data.error || 'Failed to bury');
                }
            } catch (error) {
                console.error('[BURY] Error:', error);
                alert('Failed to bury post');
            }
        });
    });
});

console.log('[16chan V3] JavaScript loaded and ready');