import streamlit as st
import requests
from PIL import Image
import io

st.set_page_config(page_title="Identity-Preserving AI Editor", layout="wide")

st.title("🛡️ Identity-Preserving Image Editor")
st.caption("Prevent multi-turn facial drift by locking face embeddings mathematically.")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Step 1: Upload Anchor Face")
    uploaded_file = st.file_uploader("Upload reference photo (Base Identity)", type=["jpg", "jpeg", "png"])
    
    if uploaded_file:
        st.image(uploaded_file, caption="Target Face (Anchor)", width=300)

    st.subheader("Step 2: Enter Scene Modification")
    prompt = st.text_area(
        "Modification Prompt", 
        value="A portrait of the person wearing a sharp blue tuxedo, standing in a brightly lit modern art gallery, cinematic lighting, 8k"
    )
    
    generate_btn = st.button("Generate Edit (Zero Drift)", type="primary", use_container_width=True)

with col2:
    st.subheader("Generated Output")
    
    if generate_btn:
        if not uploaded_file:
            st.error("Please upload a reference image first!")
        else:
            with st.spinner("Locking facial geometry & generating scene..."):
                try:
                    files = {
                        "reference_image": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)
                    }
                    data = {"prompt": prompt}
                    
                    response = requests.post("http://127.0.0.1:8000/edit", files=files, data=data)
                    
                    if response.status_code == 200:
                        output_image = Image.open(io.BytesIO(response.content))
                        st.image(output_image, caption="Modified Image (Identity Preserved)", use_column_width=True)
                        st.success("Generation completed successfully!")
                    else:
                        st.error(f"Error {response.status_code}: {response.text}")
                        
                except Exception as e:
                    st.error(f"Failed to communicate with backend server: {e}")