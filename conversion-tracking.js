(function () {
  'use strict';

  function sendEvent(eventName, parameters) {
    if (typeof window.gtag !== 'function') return;
    window.gtag('event', eventName, parameters);
  }

  function pageParameters() {
    return {
      page_path: window.location.pathname,
      page_title: document.title
    };
  }

  function ctaLocation(link) {
    if (link.dataset.ctaLocation) return link.dataset.ctaLocation;
    if (link.closest('nav')) return 'navigation';
    if (link.closest('.page-hero, .hero')) return 'hero';
    if (link.closest('footer')) return 'footer';
    if (link.closest('.cta-band')) return 'cta_band';
    return 'page_content';
  }

  function isConsultationCta(link) {
    const href = link.getAttribute('href') || '';
    if (!/^(?:https?:\/\/ysefinance\.com\.au)?\/?#contact$/.test(href)) return false;

    const label = [
      link.textContent,
      link.getAttribute('data-en'),
      link.getAttribute('data-zh')
    ].filter(Boolean).join(' ');

    return /book|consult|enquir|contact|预约|咨询|联系/i.test(label);
  }

  document.addEventListener('click', function (event) {
    const link = event.target.closest('a[href]');
    if (!link) return;

    const href = link.getAttribute('href') || '';
    const parameters = pageParameters();

    if (href.toLowerCase().startsWith('tel:')) {
      sendEvent('phone_click', Object.assign(parameters, {
        link_type: 'phone',
        cta_location: ctaLocation(link)
      }));
      return;
    }

    if (href.toLowerCase().startsWith('mailto:')) {
      sendEvent('email_click', Object.assign(parameters, {
        link_type: 'email',
        cta_location: ctaLocation(link)
      }));
      return;
    }

    if (isConsultationCta(link)) {
      sendEvent('consultation_cta_click', Object.assign(parameters, {
        link_type: 'internal_anchor',
        cta_location: ctaLocation(link),
        service_context: link.dataset.serviceContext || 'general'
      }));
    }
  });

  const enquiryForm = document.getElementById('contactForm');
  if (enquiryForm) {
    const storageKey = 'yse_form_start:' + window.location.pathname + ':' + enquiryForm.id;

    enquiryForm.addEventListener('focusin', function () {
      try {
        if (sessionStorage.getItem(storageKey)) return;
        sessionStorage.setItem(storageKey, '1');
      } catch (error) {
        if (enquiryForm.dataset.formStartTracked === 'true') return;
        enquiryForm.dataset.formStartTracked = 'true';
      }
      sendEvent('form_start', Object.assign(pageParameters(), {
        cta_location: 'contact_form',
        service_context: 'general'
      }));
    }, { once: true });
  }
}());
