"""
View to render the contact flatpage
"""

from django.shortcuts import render


def contact(request):
    """
    Function-based view that renders the contact page ``contact``

    Args:
        request (request): The request

    Returns:
        HttpResponse: Render the contact page
    """
    return render(request, "contact.html")
