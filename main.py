import streamlit as st
import hmac
import urllib.request
import json

from datetime import datetime, timedelta, timezone
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

AZURE_ACCOUNT_NAME = st.secrets["storage_account_name"]
AZURE_CONTAINER_NAME = st.secrets["container_name"]
AZURE_PRIMARY_KEY = st.secrets["storage_account_primary_key"]
AZURE_CHAT_URL = st.secrets["chat_endpoint"]
AZURE_API_KEY = st.secrets["chat_endpoint_api_key"]
AZUREML_DEPLOYMENT = st.secrets["deployment_name"]

reference_names = []
reference_pages = []
reference_text = []

blob_service_client = BlobServiceClient(
    account_url=f"https://{AZURE_ACCOUNT_NAME}.blob.core.windows.net",
    credential=DefaultAzureCredential(),
)

headers = {
    "Content-Type": "application/json",
    "Authorization": ("Bearer " + AZURE_API_KEY),
    "azureml-model-deployment": AZUREML_DEPLOYMENT,
}

st.set_page_config(layout="wide")

st.markdown(
    """
    <style>
    [data-testid="stChatMessageContent"] p{
        font-size: 1.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <style>
        [data-testid=stImage]{
            text-align: center;
            display: block;
            margin-left: auto;
            margin-right: auto;
            width: 100%;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <style>
        [data-testid=stForm]{
            text-align: center;
            display: block;
            margin-left: auto;
            margin-right: auto;
            width: 40%;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def generate_download_signed_url(
    azure_account_name, azure_container, azure_blob, azure_primary_key
):
    """
    Generate a signed URL for downloading a blob from Azure Blob Storage.

    Args:
        azure_account_name (str): The name of the Azure storage account.
        azure_container (str): The name of the container where the blob is stored.
        azure_blob (str): The name of the blob to download.
        azure_primary_key (str): The primary key of the Azure storage account.

    Returns:
        str: The signed URL for downloading the blob.
    """
    sas_blob = generate_blob_sas(
        account_name=azure_account_name,
        container_name=azure_container,
        blob_name=azure_blob,
        account_key=azure_primary_key,
        # For writing back to the Azure Blob set write and create to True
        permission=BlobSasPermissions(read=True, write=False, create=False),
        # This URL will be valid for 1 hour
        expiry=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    url = (
        "https://"
        + azure_account_name
        + ".blob.core.windows.net/"
        + azure_container
        + "/"
        + azure_blob
        + "?"
        + sas_blob
    )

    return url


def list_blobs_flat(blob_service_client, container_name):
    """
    Retrieves a list of blobs in a flat structure from the specified container in Azure Blob Storage.

    Args:
        blob_service_client (BlobServiceClient): The client object used to interact with Azure Blob Storage.
        container_name (str): The name of the container from which to retrieve the blobs.

    Returns:
        List[BlobItem]: A list of BlobItem objects representing the blobs in the container.
    """
    container_client = blob_service_client.get_container_client(
        container=container_name
    )

    blob_list = container_client.list_blobs()

    return blob_list


def check_password():
    """Returns `True` if the user had a correct password."""

    def login_form():
        """Form with widgets to collect user information"""
        st.image("./images/epa_banner.png", use_column_width="always")
        st.image("./images/epa_xplorer.png")

        with st.form("Credentials"):
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.form_submit_button("Log in", on_click=password_entered)

        message = f"<h5 style='text-align: center; color: #4e95d9;'>I AM YOUR GUIDE TO ALL GHG EMISSIONS IN EPA AND OGMP!</h5>"
        st.markdown(
            message,
            unsafe_allow_html=True,
        )

        st.write("#")
        st.write("#")
        st.image("./images/methane_iq.png")

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["username"] in st.secrets[
            "passwords"
        ] and hmac.compare_digest(
            st.session_state["password"],
            st.secrets.passwords[st.session_state["username"]],
        ):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the username or password.
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    # Return True if the username + password is validated.
    if st.session_state.get("password_correct", False):
        return True

    # Show inputs for username + password.
    login_form()
    if "password_correct" in st.session_state:
        st.error("😕 User not known or password incorrect")
    return False


if not check_password():
    st.stop()

st.image("./images/epa_banner.png", use_column_width="always")

col1, col2, col3 = st.columns([0.2, 0.6, 0.2])

with col1:
    st.subheader(
        ":blue[MY KNOWLEDGE BASE INCLUDES THE FOLLOWING DOCUMENTS FROM EPA & OGMP. I UPDATE MY INFORMATION REGULARLY:]",
        divider="gray",
    )
    container = st.container(border=True, height=800)

    with container:
        list_documents = list_blobs_flat(blob_service_client, AZURE_CONTAINER_NAME)

        list_document_copy = list(list_documents).copy()

        text_total = f"<h5 style='text-align: left; color: black;'>{len(list(list_document_copy))} Documents:</h5>"
        st.markdown(
            text_total,
            unsafe_allow_html=True,
        )

        for document in list_document_copy:
            document_path = document.name
            url = generate_download_signed_url(
                AZURE_ACCOUNT_NAME,
                AZURE_CONTAINER_NAME,
                document_path,
                AZURE_PRIMARY_KEY,
            )
            document_name = f"- [{document_path.split('/')[-1]}]"
            st.write(document_name + "(%s)" % url)

with col2:
    st.image("./images/epa_xplorer.png")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if prompt := st.chat_input("What is up?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            data = {"chat_input": prompt, "chat_history": []}
            body = str.encode(json.dumps(data))

            req = urllib.request.Request(AZURE_CHAT_URL, body, headers)

            response = urllib.request.urlopen(req)

            response_from_azure = json.loads(response.read())

            st.markdown(response_from_azure["chat_output"])

            for i in range(len(response_from_azure["references"])):
                reference_names.append(
                    response_from_azure["references"][i]["metadata"]["source"][
                        "filename"
                    ]
                )
                reference_pages.append(
                    response_from_azure["references"][i]["metadata"]["page_number"]
                )
                reference_text.append(response_from_azure["references"][i]["text"])

            with st.expander("Sources:"):
                tab1, tab2, tab3 = st.tabs(["Source 1", "Source 2", "Source 3"])
                number_sources = len(reference_text)

                if number_sources >= 1:
                    with tab1:
                        if reference_text[0] != None:
                            st.markdown(
                                f"**Document:** {reference_names[0]},  **Page:** {reference_pages[0]}"
                            )
                            st.markdown(reference_text[0])
                    if number_sources >= 2:
                        with tab2:
                            if reference_text[1] != None:
                                st.markdown(
                                    f"**Document:** {reference_names[1]},  **Page:** {reference_pages[1]}"
                                )
                                st.markdown(reference_text[1])
                        if number_sources >= 3:
                            with tab3:
                                if reference_text[2] != None:
                                    st.markdown(
                                        f"**Document:** {reference_names[2]},  **Page:** {reference_pages[2]}"
                                    )
                                    st.markdown(reference_text[2])

        st.session_state.messages.append(
            {"role": "assistant", "content": response_from_azure["chat_output"]}
        )

with col3:

    st.subheader(
        ":blue[BASED ON YOUR QUESTION, YOU MAY WANT TO LOOK AT THESE REFERENCES:]",
        divider="gray",
    )
    container = st.container(border=True)

    reference_names_copy = list(set(reference_names.copy()))

    with container:

        for reference_name in reference_names_copy:
            document_path = f"/tmp/{reference_name}"
            url = generate_download_signed_url(
                AZURE_ACCOUNT_NAME,
                AZURE_CONTAINER_NAME,
                document_path,
                AZURE_PRIMARY_KEY,
            )
            element = f"- [{reference_name}]"
            st.write(element + "(%s)" % url)
