#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "platform.h"
#include "ion.h"
#include "bp.h"
#include "rfx.h"
#include "zco.h" 

// Forward declarations of helper functions if needed

// --- Existing ION/BP/RFX Bindings ---

// Add Contact
static PyObject* emion_add_contact(PyObject* self, PyObject* args) {
    unsigned int region;
    unsigned long from_time, to_time;
    unsigned long from_node, to_node;
    unsigned long rate;
    float confidence;
    PsmAddress addr = 0;

    if (!PyArg_ParseTuple(args, "Ikkkkkf", &region, &from_time, &to_time, &from_node, &to_node, &rate, &confidence)) {
        return NULL;
    }

    if (rfx_insert_contact(region, from_time, to_time, from_node, to_node, rate, confidence, &addr, 0) < 0) {
        PyErr_SetString(PyExc_RuntimeError, "rfx_insert_contact failed");
        return NULL;
    }
    Py_RETURN_NONE;
}

// Remove Contact
static PyObject* emion_remove_contact(PyObject* self, PyObject* args) {
    unsigned int region;
    unsigned long from_time_val;
    time_t from_time;
    unsigned long from_node, to_node;

    if (!PyArg_ParseTuple(args, "Ikkk", &region, &from_time_val, &from_node, &to_node)) {
        return NULL;
    }
    from_time = (time_t)from_time_val;

    if (rfx_remove_contact(region, &from_time, from_node, to_node, 0) < 0) {
        PyErr_SetString(PyExc_RuntimeError, "rfx_remove_contact failed");
        return NULL;
    }
    Py_RETURN_NONE;
}

// Add Range
static PyObject* emion_add_range(PyObject* self, PyObject* args) {
    unsigned long from_time, to_time;
    unsigned long from_node, to_node;
    unsigned long owlt;
    PsmAddress addr = 0;

    if (!PyArg_ParseTuple(args, "kkkkk", &from_time, &to_time, &from_node, &to_node, &owlt)) {
        return NULL;
    }

    if (rfx_insert_range(from_time, to_time, from_node, to_node, owlt, &addr, 0) < 0) {
        PyErr_SetString(PyExc_RuntimeError, "rfx_insert_range failed");
        return NULL;
    }
    Py_RETURN_NONE;
}

// Remove Range
static PyObject* emion_remove_range(PyObject* self, PyObject* args) {
    unsigned long from_time_val;
    time_t from_time;
    unsigned long from_node, to_node;

    if (!PyArg_ParseTuple(args, "kkk", &from_time_val, &from_node, &to_node)) {
        return NULL;
    }
    from_time = (time_t)from_time_val;

    if (rfx_remove_range(&from_time, from_node, to_node, 0) < 0) {
        PyErr_SetString(PyExc_RuntimeError, "rfx_remove_range failed");
        return NULL;
    }
    Py_RETURN_NONE;
}

static PyObject* emion_version(PyObject* self, PyObject* args) {
    return Py_BuildValue("s", "0.0.1 (ION wrapper)");
}

static PyObject* emion_ion_attach(PyObject* self, PyObject* args) {
    if (ionAttach() < 0) {
        PyErr_SetString(PyExc_RuntimeError, "Failed to attach to ION functionality.");
        return NULL;
    }
    Py_RETURN_NONE;
}

static PyObject* emion_ion_detach(PyObject* self, PyObject* args) {
    ionDetach();
    Py_RETURN_NONE;
}

static PyObject* emion_bp_attach(PyObject* self, PyObject* args) {
    if (bp_attach() < 0) {
        PyErr_SetString(PyExc_RuntimeError, "Failed to attach to Bundle Protocol.");
        return NULL;
    }
    Py_RETURN_NONE;
}

static PyObject* emion_bp_detach(PyObject* self, PyObject* args) {
    bp_detach();
    Py_RETURN_NONE;
}

// --- NEW/UPDATED Bundle Functions ---

// Destructor for BpSAP PyCapsule
void destr_bpsap(PyObject *capsule) {
    BpSAP sap = (BpSAP)PyCapsule_GetPointer(capsule, "BpSAP");
    if (sap) {
        bp_close(sap);
    }
}

// bp_open(eid) -> BpSAP capsule
static PyObject* emion_bp_open(PyObject* self, PyObject* args) {
    char *eid;
    BpSAP sap;

    if (!PyArg_ParseTuple(args, "s", &eid)) {
        return NULL;
    }

    if (bp_open(eid, &sap) < 0) {
        PyErr_SetString(PyExc_RuntimeError, "bp_open failed");
        return NULL;
    }
    
    // Return opaque pointer as capsule
    return PyCapsule_New(sap, "BpSAP", destr_bpsap);
}

// bp_close(sap_capsule)
static PyObject* emion_bp_close(PyObject* self, PyObject* args) {
    PyObject *capsule;
    if (!PyArg_ParseTuple(args, "O", &capsule)) {
        return NULL;
    }
    
    BpSAP sap = (BpSAP)PyCapsule_GetPointer(capsule, "BpSAP");
    if (sap == NULL) {
        // Error raised by GetPointer
        return NULL;
    }

    bp_close(sap);
    
    // Invalidate capsule
    PyCapsule_SetPointer(capsule, NULL);
    
    Py_RETURN_NONE;
}

// bp_receive(sap_capsule, timeout_sec) -> (source_eid, payload_bytes) or None
static PyObject* emion_bp_receive(PyObject* self, PyObject* args) {
    PyObject *capsule;
    int timeout_sec;
    BpSAP sap;
    BpDelivery dlv;
    int result;

    if (!PyArg_ParseTuple(args, "Oi", &capsule, &timeout_sec)) {
        return NULL;
    }

    sap = (BpSAP)PyCapsule_GetPointer(capsule, "BpSAP");
    if (sap == NULL) {
        return NULL;
    }

    // Blocking receive
    // bp_receive(BpSAP sap, BpDelivery *dlv, int timeoutSeconds);
    // Allow threads while waiting (ION typically uses signals, might interrupt, but let's try)
    Py_BEGIN_ALLOW_THREADS
    result = bp_receive(sap, &dlv, timeout_sec);
    Py_END_ALLOW_THREADS

    if (result < 0) {
        PyErr_SetString(PyExc_RuntimeError, "bp_receive failed or error");
        return NULL;
    }
    
    // Check delivery result
    if (dlv.result == BpReceptionTimedOut) {
        Py_RETURN_NONE;
    }
    if (dlv.result == BpReceptionInterrupted) {
         PyErr_SetString(PyExc_RuntimeError, "BpReceptionInterrupted");
         return NULL;
    }
    if (dlv.result == BpEndpointStopped) {
         PyErr_SetString(PyExc_RuntimeError, "BpEndpointStopped");
         return NULL;
    }

    // Process delivery
    // dlv.bundleSourceEid (char*)
    // dlv.adu (Object) -> needs to be read from SDR
    Sdr sdr = getIonsdr();
    char *buffer = NULL;
    vast length = 0;
    ZcoReader reader; // Local reader
    
    if (sdr_begin_xn(sdr) < 0) {
        bp_release_delivery(&dlv, 1);
        PyErr_SetString(PyExc_RuntimeError, "SDR transaction failed in receive");
        return NULL;
    }
    
    length = zco_source_data_length(sdr, dlv.adu);
    buffer = (char*)malloc(length);
    if (buffer == NULL) {
         sdr_exit_xn(sdr);
         bp_release_delivery(&dlv, 1);
         return PyErr_NoMemory();
    }
    
    // Read formatted data
    zco_start_receiving(dlv.adu, &reader);
    // zco_receive_headers not needed for simple payload? 
    // Simplified: just read whole content
    if (zco_receive_source(sdr, &reader, length, buffer) < 0) {
        free(buffer);
        sdr_cancel_xn(sdr);
        bp_release_delivery(&dlv, 1);
        PyErr_SetString(PyExc_RuntimeError, "Failed to read bundle payload");
        return NULL;
    }
    
    sdr_exit_xn(sdr);
    
    // Build return value, use "sy#" for string + bytes with length
    PyObject *ret = Py_BuildValue("sy#", dlv.bundleSourceEid, buffer, (Py_ssize_t)length);
    free(buffer);
    
    // Release delivery
    bp_release_delivery(&dlv, 1);
    
    return ret;
}

// updated bp_send to support using a SAP or creating one
// bp_send(source_eid_or_sap, dest_eid, payload)
static PyObject* emion_bp_send(PyObject* self, PyObject* args) {
    PyObject *src_obj;
    char *source_eid = NULL;
    BpSAP sap = NULL;
    int own_sap = 0; // 1 if we opened it locally

    char *dest_eid;
    char *payload;
    Py_ssize_t payload_len;
    Object bundle_obj = 0;
    Object zco = 0;
    Sdr sdr = getIonsdr();
    Address addr;

    if (!PyArg_ParseTuple(args, "Osy#", &src_obj, &dest_eid, &payload, &payload_len)) {
        return NULL;
    }

    // Check if src_obj is a string (EID) or capsule (SAP)
    if (PyUnicode_Check(src_obj)) {
        // It's a string, open specialized SAP
        PyObject* utf8 = PyUnicode_AsUTF8String(src_obj);
        source_eid = PyBytes_AsString(utf8); // temporary reference
        
        if (bp_open(source_eid, &sap) < 0) {
             Py_DECREF(utf8);
             PyErr_SetString(PyExc_RuntimeError, "bp_open failed");
             return NULL;
        }
        own_sap = 1;
        Py_DECREF(utf8);
    } else if (PyCapsule_CheckExact(src_obj)) {
        sap = (BpSAP)PyCapsule_GetPointer(src_obj, "BpSAP");
        if (sap == NULL) return NULL;
    } else {
        PyErr_SetString(PyExc_TypeError, "First argument must be EID string or BpSAP capsule");
        return NULL;
    }

    // Start SDR transaction
    if (sdr_begin_xn(sdr) < 0) {
        if (own_sap) bp_close(sap);
        PyErr_SetString(PyExc_RuntimeError, "SDR transaction failed");
        return NULL;
    }

    // Copy data into SDR heap
    addr = sdr_malloc(sdr, payload_len);
    if (addr == 0) {
        sdr_cancel_xn(sdr);
        if (own_sap) bp_close(sap);
        PyErr_SetString(PyExc_MemoryError, "SDR malloc failed");
        return NULL;
    }
    sdr_write(sdr, addr, payload, payload_len);
    
    // Create ZCO pointing to this SDR address
    zco = zco_create(sdr, ZcoSdrSource, addr, 0, payload_len, ZcoOutbound);
    if (zco == 0) {
         sdr_cancel_xn(sdr);
         if (own_sap) bp_close(sap);
         PyErr_SetString(PyExc_RuntimeError, "ZCO create failed");
         return NULL;
    }

    // Send
    // Note: Assuming standard priority and lifespan for simplicity
    if (bp_send(sap, dest_eid, NULL, 300, BP_STD_PRIORITY, 0, 0, 0, NULL, zco, &bundle_obj) < 0) {
        if (own_sap) bp_close(sap);
        sdr_cancel_xn(sdr);
        PyErr_SetString(PyExc_RuntimeError, "bp_send failed");
        return NULL;
    }
    
    if (own_sap) bp_close(sap);

    if (sdr_end_xn(sdr) < 0) {
        PyErr_SetString(PyExc_RuntimeError, "SDR end transaction failed");
        return NULL;
    }

    return PyLong_FromUnsignedLong((unsigned long)bundle_obj);
}

// Method table update
static PyMethodDef EmionMethods[] = {
    {"version", emion_version, METH_VARARGS, "Get version string."},
    {"ion_attach", emion_ion_attach, METH_NOARGS, "Attach to ION infrastructure."},
    {"ion_detach", emion_ion_detach, METH_NOARGS, "Detach from ION infrastructure."},
    {"bp_attach", emion_bp_attach, METH_NOARGS, "Attach to BP agent."},
    {"bp_detach", emion_bp_detach, METH_NOARGS, "Detach from BP agent."},
    {"bp_open", emion_bp_open, METH_VARARGS, "Open a BP endpoint. Returns handle."},
    {"bp_close", emion_bp_close, METH_VARARGS, "Close a BP endpoint handle."},
    {"bp_receive", emion_bp_receive, METH_VARARGS, "Receive bundle from handle. Args: handle, timeout. Returns (src, payload) or None."},
    {"bp_send", emion_bp_send, METH_VARARGS, "Send a bundle. Args: source_eid_or_handle, dest, payload"},
    {"add_contact", emion_add_contact, METH_VARARGS, "Add contact. Args: region, from_time, to_time, from_node, to_node, rate, confidence"},
    {"remove_contact", emion_remove_contact, METH_VARARGS, "Remove contact. Args: region, from_time, from_node, to_node"},
    {"add_range", emion_add_range, METH_VARARGS, "Add range. Args: from_time, to_time, from_node, to_node, owlt"},
    {"remove_range", emion_remove_range, METH_VARARGS, "Remove range. Args: from_time, from_node, to_node"},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

// Module definition
static struct PyModuleDef emionmodule = {
    PyModuleDef_HEAD_INIT,
    "_core",   /* name of module */
    "ION-DTN C extension module", /* module documentation, may be NULL */
    -1,       /* size of per-interpreter state of the module,
                 or -1 if the module keeps state in global variables. */
    EmionMethods
};

// Module initialization
PyMODINIT_FUNC PyInit__core(void) {
    return PyModule_Create(&emionmodule);
}
