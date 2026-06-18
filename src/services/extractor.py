import pymupdf
import json
from pathlib import Path
import tempfile

from src.services.logging import create_logger
from src.schemas.extractor import PageContent, PDFContent
from src.api.core.exception import PDFDecryptionError, PDFPermissionError


logger = create_logger()
file_path = "/Users/indicina/Downloads/bw_anmeldebestaetigung_20260511093901_1.pdf"

def encryption_check(pdf_file: pymupdf.Document) -> bool:
    """
    This function checks if the PDF file is encrypted. It logs the encryption status of the PDF 
    file and returns a boolean value indicating whether decryption is required before text extraction. 

    Args:
        pdf_file (pymupdf.Document): The PDF file to be checked for encryption.

    Returns:
        bool: True if the PDF file is encrypted and decryption is required before text extraction, 
          False if the PDF file is not encrypted and text extraction can proceed without decryption. 
    """
    doc_name = str(pdf_file.name).split("/")[-1]
    if not pdf_file.is_encrypted:
        logger.info("%s is not encrypted. Proceeding with text extraction.", doc_name)
        return False
    logger.info("%s is encrypted. Decryption required before text extraction.", doc_name)
    return True

def convert_to_pdf(file: pymupdf.Document, temp_dir: Path) -> Path:
    """
    This function converts Non-pdf files to PDF format. It takes a file path as input and returns the path to the converted PDF file.

    Args:
        file (pymupdf.Document): The file to be converted to PDF format.
    
    Returns:
  
    """
    doc_name = str(file.name).split("/")[-1]
    logger.info("Converting %s to PDF format...", doc_name)
    pdf_bytes = file.convert_to_pdf()
    converted_pdf_path = temp_dir / f"converted_{doc_name}.pdf"
    pdf_doc = pymupdf.open("pdf", pdf_bytes)
    pdf_doc.save(converted_pdf_path)
    logger.info("Conversion completed for %s.", doc_name)
    return converted_pdf_path


def get_pdf_permissions(pdf_file: pymupdf.Document) -> bool:
    """
    This function checks the extraction and copy permission status of a decrypted to ensure copyright compliance.

    Args:
        pdf_file (pymupdf.Document): The decrypted pdf file

    Returns:
        extraction_allowed (bool): Returns True if permission is granted for extraction and copying but False if restricted 
    """
    pdf_permissions = pdf_file.permissions
    extract_persmissions = getattr(pymupdf, "PDF_PERM_COPY")   # Permission to copy or extract text and graphics from the PDF
    extraction_allowed = bool(pdf_permissions & extract_persmissions)
    return extraction_allowed


def pdf_decryption(pdf_file: pymupdf.Document, password: str = "", allow_permission_warning=True) -> pymupdf.Document:
    """
    This function attempts to decrypt the PDF file if it is encrypted. It checks for the presence of a password and 
    attempts decryption accordingly. If decryption is successful but text extraction is not allowed by PDF permissions, 
    it logs a warning message.

    Args:
        pdf_file (pymupdf.Document): The PDF file to be decrypted.
        request_id (str): A unique identifier for the request, used for logging purposes.
        password (str): The password to be used for decryption if the PDF is encrypted with a password.
        allow_permission_warning (bool): Flag to determine whether to log a warning if decryption is successful 
           but text extraction is not allowed by PDF permissions. Default is True.

    Returns:
    
    """
    doc_name = str(pdf_file.name).split("/")[-1]
    logger.info(f"Attempting to decrypt {doc_name}...")

    # check if the PDF file is encrypted and requires a password for decryption
    if pdf_file.needs_pass:
        logger.info("%s is encrypted with a password. Attempting to decrypt with password.", doc_name)

        if not password:
            logger.error("No password provided for %s. Unable to proceed with decryption.", doc_name)
            raise PDFDecryptionError(details="Password is required for encrypted PDF, but no password was provided.")
        
        logger.info("Decrypting %s with provided password.", doc_name)
        decryption_result = pdf_file.authenticate(password)
        
        # Authorization Check: If decryption fails due to incorrect password, log an error and do not 
        # proceed with text extraction
        if decryption_result == 0:
            logger.error("Decryption failed for %s. Incorrect password provided.", doc_name)
            raise PDFDecryptionError(details="Incorrect password provided for encrypted PDF. Decryption failed.")
        
        logger.info("Decryption successful for %s. Proceeding with text extraction.", doc_name)
        return pdf_file

    # Decrypt pdf file that is encrypted but does not require a password 
    # (e.g., encrypted with an empty password or has permissions set to restrict access without a password)   
    logger.info("%s is encrypted but does not require a password. Attempting to decrypt without password...", doc_name)
    decryption_result = pdf_file.authenticate("")
    
    # Check if decryption attempt
    if decryption_result == 0:
        logger.error("Decryption failed for %s. Cannot proceed.", doc_name)
        raise PDFDecryptionError(details="Decryption failed for encrypted PDF. Cannot proceed.")
    
    logger.info("Decryption successful for %s.", doc_name)

    # Authorization Check: Warn if decryption is successful but text extraction is not allowed by PDF permissions
    # To be replaced with a more robust permission handling mechanism in the future (e.g., user permissions, document owner settings, etc.)
    extraction_allowed = get_pdf_permissions(pdf_file)
    if not extraction_allowed and allow_permission_warning:
        logger.error("Text extraction is not allowed for %s. Contact the document owner for permission changes.", doc_name)
        raise PDFPermissionError(
            details="Text extraction is not allowed for this PDF. Contact the document owner for permission changes."
        )
          
    return pdf_file
    


def pdf_text_extractor(file_path: Path, password="") -> PDFContent:
    with tempfile.TemporaryDirectory() as temp_dir:
        doc = pymupdf.open(file_path)
        if not doc.is_pdf:
            file_path = convert_to_pdf(doc, Path(temp_dir))
            doc = pymupdf.open(file_path)
        
        is_encrypted = encryption_check(doc)
        if is_encrypted:
            doc = pdf_decryption(doc, password=password)

        doc_name = str(doc.name).split("/")[-1]
        extracted_pages: list[PageContent] = []

        logger.info("Extracting text from %s...", doc_name)
        for page_index in range(len(doc)): 
            page = doc[page_index]
            page_text = page.get_text('dict', sort=True)
            extracted_page = PageContent.model_validate(
                {
                    "page_number": page_index + 1, 
                    **page_text # type: ignore
                } 
            )
            extracted_pages.append(extracted_page)
        
        pdf_content = PDFContent(
            job_id = doc_name,
            total_pages = len(doc),
            pages=extracted_pages
        )
        
        logger.info("Text extraction completed for %s.", doc_name)
        return pdf_content


def translate_doc(from_lang: str, to_lang: str):
    pass
# """Try block and line bbox for now for pdf recreation"""
# if __name__ == "__main__":
#     file_path = "/Users/indicina/Downloads/bw_anmeldebestaetigung_20260511093901_1.pdf"

#     doc = pymupdf.open(file_path)
#     extracted_pages: list[PageContent] = []

#     for page_index in range(len(doc)): 
#         if page_index < 20:    
#             # print("page: ", page_index + 1)
#             page = doc[page_index]
#             page_text = page.get_text('dict', sort=True)
#             extracted_page = PageContent.model_validate(
#                 {"page_number": page_index + 1, **page_text} # type: ignore
#             )
#             extracted_pages.append(extracted_page)
    
#     pdf_content = PDFContent(pages=extracted_pages, total_pages=len(doc), job_id="test_job_id")
#     with open("extracted_content_structured.json", "w", encoding="utf-8") as f:
#         json.dump(pdf_content.model_dump(), f, indent=4, ensure_ascii=False)
