document.addEventListener("DOMContentLoaded", () => {
  const addressApi = {
    provinces: "/purchasing/address/provinces",
    cities: "/purchasing/address/cities",
    barangays: "/purchasing/address/barangays",
  };

  const parseNumber = (value) => {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : 0;
  };

  const formatMoney = (value) => {
    const parsed = parseNumber(value);
    return parsed ? parsed.toFixed(2) : "";
  };

  if (window.Swal) {
    document.querySelectorAll("[data-flash-message]").forEach((messageEl) => {
      const category = messageEl.dataset.flashCategory || "info";
      const message = messageEl.dataset.flashMessage || messageEl.textContent.trim();
      messageEl.remove();
      Swal.fire({
        toast: true,
        position: "top-end",
        icon: category === "danger" ? "error" : category,
        title: message,
        showConfirmButton: false,
        timer: 2800,
        timerProgressBar: true,
      });
    });
  }

  const initSelect2 = (element, parent) => {
    if (window.jQuery && window.jQuery.fn && window.jQuery.fn.select2 && element) {
      window.jQuery(element).select2({
        width: "100%",
        dropdownParent: parent ? window.jQuery(parent) : undefined,
      });
    }
  };

  const initRemoteSelect2 = async (element, parent, url, extraParams = {}) => {
    if (!(window.jQuery && window.jQuery.fn && window.jQuery.fn.select2 && element)) {
      return [];
    }
    const params = typeof extraParams === "function" ? extraParams() : extraParams;
    const query = new URLSearchParams(params || {}).toString();
    const response = await fetch(`${url}${query ? `?${query}` : ""}`, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    const data = await response.json();
    const results = Array.isArray(data?.results) ? data.results : [];
    const $element = window.jQuery(element);
    if ($element.data("select2")) {
      $element.select2("destroy");
    }
    const currentValue = element.value;
    element.innerHTML = '<option value=""></option>';
    results.forEach((item) => {
      if (item && item.id !== undefined) {
        element.add(new Option(item.text || item.id, item.id, false, false));
      }
    });
    $element.select2({
      width: "100%",
      dropdownParent: parent ? window.jQuery(parent) : undefined,
      placeholder: element.dataset.placeholder || "Select an option",
      allowClear: true,
    });
    if (currentValue) {
      $element.val(currentValue).trigger("change.select2");
    }
    return results;
  };

  document.querySelectorAll("form[data-pr-form]").forEach((form) => {
    const partnerTypeSelect = form.querySelector("[data-pr-partner-type]");
    const partnerPanels = Array.from(form.querySelectorAll("[data-pr-partner-panel]"));
    const partnerSelects = Array.from(form.querySelectorAll("[data-pr-partner-select]"));
    const addressField = form.querySelector("[data-pr-address]");
    const lineBody = form.querySelector("[data-pr-line-body]");
    const addLineButton = form.querySelector("[data-pr-add-line]");
    const lineTemplate = document.getElementById("pr-line-template");

    const togglePartnerPanels = () => {
      const type = partnerTypeSelect ? partnerTypeSelect.value : "supplier";
      partnerPanels.forEach((panel) => {
        panel.classList.toggle("d-none", panel.dataset.prPartnerPanel !== type);
      });
      partnerSelects.forEach((select) => {
        if (select.closest("[data-pr-partner-panel]")?.dataset.prPartnerPanel !== type) {
          select.value = "";
        }
      });
      updateAddressFromSelection();
    };

    const updateAddressFromSelection = () => {
      const activeSelect = partnerSelects.find((select) => !select.closest("[data-pr-partner-panel]")?.classList.contains("d-none"));
      if (!activeSelect || !addressField) {
        return;
      }
      const selectedOption = activeSelect.options[activeSelect.selectedIndex];
      addressField.value = selectedOption?.dataset.address || "";
    };

    const updateLineTotals = (line) => {
      const quantityField = line.querySelector("[name='line_quantity']");
      const unitPriceField = line.querySelector("[name='line_unit_price']");
      const totalField = line.querySelector("[name='line_total_preview']");
      if (!quantityField || !unitPriceField || !totalField) {
        return;
      }
      const total = parseNumber(quantityField.value) * parseNumber(unitPriceField.value);
      totalField.value = total ? total.toFixed(2) : "";
    };

    const updateLineFromProduct = (line) => {
      const productSelect = line.querySelector("[data-pr-product-select]");
      if (!productSelect) {
        return;
      }
      const option = productSelect.options[productSelect.selectedIndex];
      line.querySelector("[name='line_sku_snapshot']").value = option?.dataset.sku || "";
      line.querySelector("[name='line_name_snapshot']").value = option?.dataset.name || "";
      line.querySelector("[name='line_uom_snapshot']").value = option?.dataset.uom || "";
      const unitPriceField = line.querySelector("[name='line_unit_price']");
      if (unitPriceField && !unitPriceField.value) {
        unitPriceField.value = option?.dataset.price ? formatMoney(option.dataset.price) : "";
      }
      updateLineTotals(line);
    };

    const wireLine = (line) => {
      const productSelect = line.querySelector("[data-pr-product-select]");
      const quantityField = line.querySelector("[name='line_quantity']");
      const unitPriceField = line.querySelector("[name='line_unit_price']");
      const removeButton = line.querySelector("[data-pr-remove-line]");

      if (productSelect) {
        productSelect.addEventListener("change", () => updateLineFromProduct(line));
      }
      if (quantityField) {
        quantityField.addEventListener("input", () => updateLineTotals(line));
      }
      if (unitPriceField) {
        unitPriceField.addEventListener("input", () => updateLineTotals(line));
      }
      if (removeButton) {
        removeButton.addEventListener("click", () => {
          if (lineBody && lineBody.children.length > 1) {
            line.remove();
          }
        });
      }
    };

    const addLine = () => {
      if (!lineTemplate || !lineBody) {
        return;
      }
      const fragment = lineTemplate.content.cloneNode(true);
      const line = fragment.querySelector("[data-pr-line]");
      if (!line) {
        return;
      }
      lineBody.appendChild(fragment);
      const createdLine = lineBody.lastElementChild;
      wireLine(createdLine);
      const quantityField = createdLine.querySelector("[name='line_quantity']");
      if (quantityField && !quantityField.value) {
        quantityField.value = "1";
      }
      updateLineFromProduct(createdLine);
    };

    if (partnerTypeSelect) {
      partnerTypeSelect.addEventListener("change", togglePartnerPanels);
    }
    partnerSelects.forEach((select) => {
      select.addEventListener("change", updateAddressFromSelection);
    });
    if (addLineButton) {
      addLineButton.addEventListener("click", addLine);
    }

    if (lineBody && lineBody.children.length === 0) {
      addLine();
    } else if (lineBody) {
      Array.from(lineBody.querySelectorAll("[data-pr-line]")).forEach((line) => wireLine(line));
    }
    togglePartnerPanels();
    if (lineBody) {
      Array.from(lineBody.querySelectorAll("[data-pr-line]")).forEach((line) => {
        updateLineFromProduct(line);
      });
    }
  });

  const partnerModalEl = document.getElementById("partnerModal");
  if (partnerModalEl && window.bootstrap) {
    const partnerModal = new bootstrap.Modal(partnerModalEl);
    const partnerModalForm = document.getElementById("partnerModalForm");
    const partnerModalTitle = document.getElementById("partnerModalTitle");
    const partnerModalAction = document.getElementById("partnerModalAction");
    const partnerModalId = document.getElementById("partnerModalId");
    const partnerModalName = document.getElementById("partnerModalName");
    const partnerModalEmail = document.getElementById("partnerModalEmail");
    const partnerModalPhone = document.getElementById("partnerModalPhone");
    const partnerModalAddress = document.getElementById("partnerModalAddress");
    const partnerModalType = document.getElementById("partnerModalType");
    const partnerModalScope = document.getElementById("partnerModalScope");
    const addressPanels = Array.from(partnerModalEl.querySelectorAll("[data-address-panel]"));
    const countrySelect = document.getElementById("partnerModalCountry");
    const provinceSelect = document.getElementById("partnerModalProvince");
    const citySelect = document.getElementById("partnerModalCity");
    const barangaySelect = document.getElementById("partnerModalBarangay");
    const streetInput = document.getElementById("partnerModalStreet");
    const privateAddress = document.getElementById("partnerModalPrivateAddress");
    const localPreview = document.getElementById("partnerModalLocalPreview");

    const getSelectedLabel = (select) => {
      if (!select) {
        return "";
      }
      const option = select.options[select.selectedIndex];
      return (option?.textContent || option?.text || "").trim();
    };

    const findMatchingOption = (options, needle) => {
      const target = (needle || "").toLowerCase().trim();
      if (!target) {
        return null;
      }
      return options.find((option) => {
        const text = (option?.text || "").toLowerCase().trim();
        return text === target || text.includes(target) || target.includes(text);
      }) || null;
    };

    const setSelectTextValue = (select, value, label) => {
      if (!select) {
        return;
      }
      const normalizedValue = value || label || "";
      if (!normalizedValue) {
        select.value = "";
        if (window.jQuery) {
          window.jQuery(select).val(null).trigger("change.select2");
        }
        return;
      }
      const option = new Option(label || normalizedValue, normalizedValue, true, true);
      select.add(option);
      select.value = normalizedValue;
      if (window.jQuery) {
        window.jQuery(select).trigger("change.select2");
      } else {
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
    };

    const toggleDependentAddressFields = () => {
      if (citySelect) {
        citySelect.disabled = !provinceSelect?.value;
      }
      if (barangaySelect) {
        barangaySelect.disabled = !citySelect?.value;
      }
    };

    const composeAddress = () => {
      const scope = partnerModalScope?.value || "local";
      if (scope === "private") {
        return (privateAddress?.value || "").trim();
      }
      const country = getSelectedLabel(countrySelect);
      const province = getSelectedLabel(provinceSelect);
      const city = getSelectedLabel(citySelect);
      const barangay = getSelectedLabel(barangaySelect);
      if (!city) {
        return "";
      }
      const parts = [
        streetInput?.value.trim(),
        barangay,
        city,
        province,
        country,
      ].filter(Boolean);
      return parts.join(", ");
    };

    const updateAddressPanel = () => {
      const scope = partnerModalScope?.value || "local";
      addressPanels.forEach((panel) => {
        panel.classList.toggle("d-none", panel.dataset.addressPanel !== scope);
      });
      const composed = composeAddress();
      if (partnerModalAddress) {
        partnerModalAddress.value = composed;
      }
      if (localPreview && scope === "local") {
        localPreview.textContent = composed || "Select the location fields to generate the final address.";
      }
      if (partnerModalForm) {
        partnerModalForm.setAttribute("data-confirm", scope === "private" ? "Save this partner record?" : "Save this local partner address?");
      }
    };

    document.querySelectorAll("[data-partner-modal-trigger]").forEach((button) => {
      button.addEventListener("click", async () => {
        const action = button.dataset.partnerAction || "create_partner";
        const isEdit = action === "update_partner";
        if (partnerModalForm) {
          partnerModalForm.setAttribute("data-confirm", isEdit ? "Save changes to this partner?" : "Create this partner record?");
        }
        if (partnerModalTitle) {
          partnerModalTitle.textContent = button.dataset.partnerTitle || (isEdit ? "Edit Partner" : "Create Partner");
        }
        if (partnerModalAction) partnerModalAction.value = action;
        if (partnerModalId) partnerModalId.value = button.dataset.partnerId || "";
        if (partnerModalName) partnerModalName.value = button.dataset.partnerName || "";
        if (partnerModalEmail) partnerModalEmail.value = button.dataset.partnerEmail || "";
        if (partnerModalPhone) partnerModalPhone.value = button.dataset.partnerPhone || "";
        if (partnerModalType) partnerModalType.value = button.dataset.partnerType || "supplier";
        if (partnerModalScope) partnerModalScope.value = button.dataset.partnerScope || "local";
        if (privateAddress) privateAddress.value = partnerModalScope?.value === "private" ? (button.dataset.partnerAddress || "") : "";
        if (countrySelect) {
          setSelectTextValue(countrySelect, "PH", "Philippines");
        }
        if (provinceSelect) {
          window.jQuery?.(provinceSelect).val(null).trigger("change.select2");
        }
        if (citySelect) {
          window.jQuery?.(citySelect).val(null).trigger("change.select2");
        }
        if (barangaySelect) {
          window.jQuery?.(barangaySelect).val(null).trigger("change.select2");
        }
        if (streetInput) streetInput.value = "";
        const existingAddress = button.dataset.partnerAddress || "";
        let provinceGuess = "";
        let cityGuess = "";
        let barangayGuess = "";
        if (existingAddress && partnerModalScope?.value !== "private") {
          provinceGuess = existingAddress.match(/([^,]+(?:Province|Metro Manila|Region [A-Z0-9]+|District [A-Z0-9]+)?)/i)?.[1]?.trim() || "";
          cityGuess = existingAddress.split(",").map((part) => part.trim()).find((part) => /City|Municipality|Cebu|Manila|Makati|Quezon|Pasig/i.test(part)) || "";
          barangayGuess = existingAddress.split(",").map((part) => part.trim()).find((part) => /^Barangay\s|^Brgy\.?/i.test(part) || /Bel-Air|Poblacion|San Isidro|Batasan Hills|Commonwealth|Loyola Heights|Kapitolyo|San Antonio|Manggahan|Binondo|Malate|Sampaloc/i.test(part)) || "";
          const streetGuess = existingAddress
            .replace(barangayGuess || "", "")
            .replace(cityGuess || "", "")
            .replace(provinceGuess || "", "")
            .replace("Philippines", "")
            .replace(/,+/g, ",")
            .trim()
            .replace(/^,|,$/g, "");
          if (streetInput) {
            streetInput.value = streetGuess;
          }
        }
        let provinceResults = [];
        let cityResults = [];
        let barangayResults = [];
        if (provinceSelect) {
          provinceResults = await initRemoteSelect2(provinceSelect, partnerModalEl, addressApi.provinces);
          if (provinceGuess) {
            const provinceMatch = findMatchingOption(provinceResults, provinceGuess);
            if (provinceMatch) {
              setSelectTextValue(provinceSelect, provinceMatch.id, provinceMatch.text);
            }
          }
        }
        if (citySelect) {
          const provinceValue = provinceSelect?.value || "";
          if (provinceValue) {
            cityResults = await initRemoteSelect2(citySelect, partnerModalEl, addressApi.cities, () => ({ province: provinceValue }));
          }
          if (cityGuess) {
            const cityMatch = findMatchingOption(cityResults, cityGuess);
            if (cityMatch) {
              setSelectTextValue(citySelect, cityMatch.id, cityMatch.text);
            }
          }
        }
        if (barangaySelect) {
          const provinceValue = provinceSelect?.value || "";
          const cityValue = citySelect?.value || "";
          if (provinceValue || cityValue) {
            barangayResults = await initRemoteSelect2(barangaySelect, partnerModalEl, addressApi.barangays, () => ({
              province: provinceValue,
              city: cityValue,
            }));
          }
          if (barangayGuess) {
            const barangayMatch = findMatchingOption(barangayResults, barangayGuess);
            if (barangayMatch) {
              setSelectTextValue(barangaySelect, barangayMatch.id, barangayMatch.text);
            }
          }
        }
        toggleDependentAddressFields();
        updateAddressPanel();
        partnerModal.show();
      });
    });

    if (countrySelect) {
      initSelect2(countrySelect, partnerModalEl);
      countrySelect.addEventListener("change", () => {
        updateAddressPanel();
      });
    }
    if (provinceSelect) {
      provinceSelect.addEventListener("change", async () => {
        if (window.jQuery) window.jQuery(citySelect).val(null).trigger("change.select2");
        if (window.jQuery) window.jQuery(barangaySelect).val(null).trigger("change.select2");
        if (citySelect) {
          citySelect.disabled = !provinceSelect?.value;
        }
        if (barangaySelect) {
          barangaySelect.disabled = true;
        }
        if (provinceSelect.value) {
          await initRemoteSelect2(citySelect, partnerModalEl, addressApi.cities, () => ({ province: provinceSelect.value }));
          if (citySelect) {
            citySelect.disabled = false;
          }
        }
        toggleDependentAddressFields();
        updateAddressPanel();
      });
    }
    if (citySelect) {
      citySelect.addEventListener("change", async () => {
        if (window.jQuery) window.jQuery(barangaySelect).val(null).trigger("change.select2");
        if (citySelect.value) {
          await initRemoteSelect2(barangaySelect, partnerModalEl, addressApi.barangays, () => ({
            province: provinceSelect?.value || "",
            city: citySelect?.value || "",
          }));
          if (barangaySelect) {
            barangaySelect.disabled = false;
          }
        }
        toggleDependentAddressFields();
        updateAddressPanel();
      });
    }
    if (barangaySelect) {
      barangaySelect.addEventListener("change", updateAddressPanel);
    }
    if (streetInput) streetInput.addEventListener("input", updateAddressPanel);
    if (privateAddress) privateAddress.addEventListener("input", updateAddressPanel);
    if (partnerModalScope) {
      partnerModalScope.addEventListener("change", () => {
        updateAddressPanel();
      });
    }

    toggleDependentAddressFields();
  }

  const populateCheckboxGroup = (container, selectedIds, selector = 'input[type="checkbox"]') => {
    if (!container) {
      return;
    }
    const ids = new Set((selectedIds || []).map(String));
    container.querySelectorAll(selector).forEach((checkbox) => {
      checkbox.checked = ids.has(String(checkbox.value));
    });
  };

  const userEditModalEl = document.getElementById("editUserModal");
  if (userEditModalEl && window.bootstrap) {
    userEditModalEl.addEventListener("show.bs.modal", (event) => {
      const trigger = event.relatedTarget;
      if (!trigger) {
        return;
      }
      const userId = userEditModalEl.querySelector("#editUserId");
      const userName = userEditModalEl.querySelector("#editUserName");
      const userEmail = userEditModalEl.querySelector("#editUserEmail");
      const userActive = userEditModalEl.querySelector("#editUserActive");
      const userRoles = userEditModalEl.querySelector("#editUserRoles");
      const roleIds = (trigger.dataset.userRoleIds || "")
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);

      if (userId) userId.value = trigger.dataset.userId || "";
      if (userName) userName.value = trigger.dataset.userName || "";
      if (userEmail) userEmail.value = trigger.dataset.userEmail || "";
      if (userActive) userActive.checked = trigger.dataset.userActive === "1";
      if (userRoles) {
        Array.from(userRoles.options).forEach((option) => {
          option.selected = roleIds.includes(String(option.value));
        });
      }
    });
  }

  const roleEditModalEl = document.getElementById("editRoleModal");
  if (roleEditModalEl && window.bootstrap) {
    roleEditModalEl.addEventListener("show.bs.modal", (event) => {
      const trigger = event.relatedTarget;
      if (!trigger) {
        return;
      }
      const roleId = roleEditModalEl.querySelector("#editRoleId");
      const roleName = roleEditModalEl.querySelector("#editRoleName");
      const permissionIds = (trigger.dataset.rolePermissionIds || "")
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);

      if (roleId) roleId.value = trigger.dataset.roleId || "";
      if (roleName) roleName.value = trigger.dataset.roleName || "";
      populateCheckboxGroup(roleEditModalEl, permissionIds, 'input[name="permission_ids"]');
    });
  }

  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.Swal) {
        return;
      }
      if (form.dataset.confirmed === "true") {
        form.dataset.confirmed = "";
        return;
      }
      event.preventDefault();
      Swal.fire({
        title: form.dataset.confirmTitle || "Are you sure?",
        text: form.dataset.confirm || "Please confirm this action.",
        icon: form.dataset.confirmIcon || "question",
        showCancelButton: true,
        confirmButtonText: form.dataset.confirmButton || "Yes, continue",
        cancelButtonText: "Cancel",
        confirmButtonColor: "#435ebe",
      }).then((result) => {
        if (result.isConfirmed) {
          form.dataset.confirmed = "true";
          form.requestSubmit ? form.requestSubmit() : form.submit();
        }
      });
    });
  });
});
