import dns.resolver
import re
import logging
import socket
from email.utils import parseaddr
import concurrent.futures
from tqdm import tqdm

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EmailVerifier:
    """
    Comprehensive email verification system that validates email addresses using multiple methods.
    
    This class implements a multi-step verification process:
    1. Syntax validation - Checks if the email format is valid
    2. Domain validation - Verifies the domain exists via DNS lookups
    3. MX record checking - Confirms the domain can receive email
    4. Suspicious domain detection - Identifies potentially risky email domains
    
    The verification can be performed on individual emails or in batch mode with
    multithreading for efficient processing of large recipient lists.
    """
    
    def __init__(self, timeout=10):
        """
        Initialize the email verifier.
        
        Args:
            timeout (int): Timeout in seconds for DNS lookups and socket operations
        """
        self.timeout = timeout
        self.results = {
            'valid': [],
            'invalid': [],
            'risky': []  # For emails that pass syntax but have questionable domains
        }
    
    def verify_syntax(self, email):
        """
        Check if the email has valid syntax.
        
        Args:
            email (str): Email address to verify
            
        Returns:
            bool: True if syntax is valid, False otherwise
        """
        # Simple regex for email validation
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            return False
        
        # Check the email using parseaddr for more advanced validation
        _, addr = parseaddr(email)
        if addr != email:
            return False
        
        return True
    
    def verify_domain(self, domain):
        """
        Verify if the domain exists by checking its DNS records.
        
        This method attempts to resolve MX records first, then falls back to A records
        if no MX records are found, which is valid for some mail servers.
        
        Args:
            domain (str): The domain part of the email address
            
        Returns:
            tuple: (domain_exists, records) where domain_exists is a boolean and
                  records contains the DNS records if found
        """
        try:
            # Try to get MX records
            mx_records = dns.resolver.resolve(domain, 'MX')
            if mx_records:
                return True, mx_records
            return False, None
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            try:
                # Try to get A records as fallback
                a_records = dns.resolver.resolve(domain, 'A')
                if a_records:
                    return True, a_records
                return False, None
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
                return False, None
    
    def verify_email(self, email):
        """
        Verify an email address for validity.
        
        Performs a multi-step verification process:
        1. Syntax check
        2. Domain existence
        3. Suspicious domain check
        
        Args:
            email (str): Email address to verify
            
        Returns:
            tuple: (status, message) where status is one of 'valid', 'invalid', or 'risky'
                  and message provides details about the verification result
        """
        # Check syntax first (cheap operation)
        if not self.verify_syntax(email):
            logger.info(f"Invalid syntax: {email}")
            return 'invalid', "Invalid email syntax"
        
        # Extract the domain
        _, domain = email.split('@', 1)
        
        # Check domain existence
        domain_exists, records = self.verify_domain(domain)
        if not domain_exists:
            logger.info(f"Invalid domain: {domain} for {email}")
            return 'invalid', "Domain does not exist"
        
        # Check for disposable or suspicious domains
        suspicious_domains = ['mailinator.com', 'tempmail.com', 'fake.com', 'yopmail.com']
        if any(d in domain.lower() for d in suspicious_domains):
            logger.info(f"Risky domain: {domain} for {email}")
            return 'risky', "Disposable or suspicious email domain"
        
        # If everything passes, consider the email valid
        logger.info(f"Valid email: {email}")
        return 'valid', "Email passed all verification checks"
    
    def batch_verify_emails(self, emails, max_workers=10):
        """
        Verify a batch of emails using multithreading for efficiency.
        
        This is the recommended method when verifying multiple email addresses
        as it efficiently processes them in parallel.
        
        Args:
            emails (list): List of email addresses to verify
            max_workers (int): Maximum number of threads to use
            
        Returns:
            dict: Dictionary mapping email addresses to verification results
                 in the format {email: {'is_valid': bool, 'status': str, 'message': str}}
        """
        results = {}
        
        # Use ThreadPoolExecutor for parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Create a future for each email
            future_to_email = {executor.submit(self.verify_email, email): email for email in emails}
            
            # Process as they complete
            for future in concurrent.futures.as_completed(future_to_email):
                email = future_to_email[future]
                try:
                    status, message = future.result()
                    results[email] = {
                        'is_valid': status == 'valid',
                        'status': status,
                        'message': message
                    }
                except Exception as e:
                    logger.error(f"Error verifying {email}: {str(e)}")
                    results[email] = {
                        'is_valid': False,
                        'status': 'error',
                        'message': f"Verification error: {str(e)}"
                    }
        
        return results
    
    def batch_verify(self, emails, max_workers=10):
        """
        Verify a batch of emails using multithreading for efficiency.
        
        Categorizes emails into valid, invalid, and risky categories.
        
        Args:
            emails (list): List of email addresses to verify
            max_workers (int): Maximum number of threads to use
            
        Returns:
            dict: Dictionary with 'valid', 'invalid', and 'risky' lists
        """
        self.results = {
            'valid': [],
            'invalid': [],
            'risky': []
        }
        
        logger.info(f"Starting batch verification of {len(emails)} emails")
        
        # Use ThreadPoolExecutor for parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Create a future for each email
            future_to_email = {executor.submit(self.verify_email, email): email for email in emails}
            
            # Process as they complete with a progress bar
            with tqdm(total=len(emails), desc="Verifying emails") as pbar:
                for future in concurrent.futures.as_completed(future_to_email):
                    email = future_to_email[future]
                    try:
                        status, message = future.result()
                        self.results[status].append(email)
                    except Exception as e:
                        logger.error(f"Error verifying {email}: {str(e)}")
                        self.results['invalid'].append(email)
                    pbar.update(1)
        
        logger.info(f"Email verification completed. Valid: {len(self.results['valid'])}, " 
                    f"Invalid: {len(self.results['invalid'])}, Risky: {len(self.results['risky'])}")
        
        return self.results
    
    def get_verification_summary(self):
        """
        Get a summary of the verification results.
        
        Returns:
            dict: Summary statistics about the verification process
        """
        if not any(self.results.values()):
            return "No verification has been performed yet."
        
        return {
            "total_processed": sum(len(v) for v in self.results.values()),
            "valid": len(self.results['valid']),
            "invalid": len(self.results['invalid']),
            "risky": len(self.results['risky']),
            "valid_percentage": round(len(self.results['valid']) / sum(len(v) for v in self.results.values()) * 100, 2)
        }

# Example usage
if __name__ == "__main__":
    verifier = EmailVerifier()
    
    # Single email verification
    status, message = verifier.verify_email("test@example.com")
    print(f"Status: {status}, Message: {message}")
    
    # Batch verification
    test_emails = [
        "valid@gmail.com",
        "invalid@nonexistentdomain123456789.com",
        "missingatsign.com",
        "test@mailinator.com",
        "info@microsoft.com"
    ]
    
    results = verifier.batch_verify(test_emails)
    print("\nVerification Results:")
    print(f"Valid: {results['valid']}")
    print(f"Invalid: {results['invalid']}")
    print(f"Risky: {results['risky']}")
    
    summary = verifier.get_verification_summary()
    print("\nSummary:", summary)
