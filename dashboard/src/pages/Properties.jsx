import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Plus, Building2, Pencil, Trash2, X, Bed, Bath, Maximize2, MapPin, Tag } from 'lucide-react'

// Curated Unsplash real estate photos — one per slot, cycles if more than 10 properties
const LISTING_PHOTOS = [
  'photo-1564013799919-ab600027ffc6', // modern house exterior
  'photo-1613490493576-7fde63acd811', // luxury home
  'photo-1600585154340-be6161a56a0c', // beautiful suburban house
  'photo-1568605114967-8130f3a36994', // classic american home
  'photo-1600596542815-ffad4c1539a9', // pool house
  'photo-1545324418-cc1a3fa10c00',    // high-rise apartment
  'photo-1512917774080-9991f1c4c750', // condo building
  'photo-1493809842364-78817add7ffb', // modern condo interior
  'photo-1583608205776-bfd35f0d9f83', // executive estate
  'photo-1558618666-fcd25c85cd64',    // townhouse row
]

function photoUrl(index) {
  const id = LISTING_PHOTOS[index % LISTING_PHOTOS.length]
  return `https://images.unsplash.com/${id}?w=480&h=240&fit=crop&auto=format&q=80`
}

const STATUS_COLORS = {
  active:     'bg-green-50 text-green-700 border-green-200',
  pending:    'bg-amber-50 text-amber-700 border-amber-200',
  sold:       'bg-gray-100 text-gray-500 border-gray-200',
  off_market: 'bg-red-50 text-red-700 border-red-200',
}

const TYPE_LABELS = {
  house: 'House', condo: 'Condo', apartment: 'Apt',
  townhouse: 'Townhouse', land: 'Land', commercial: 'Commercial',
}

const EMPTY_FORM = {
  title: '', address: '', city: '', state: '', zip: '',
  property_type: 'house', bedrooms: '', bathrooms: '', sqft: '',
  price: '', status: 'active', description: '', mls_number: '',
}

function PropertyModal({ property, onClose, onSave }) {
  const [form, setForm] = useState(property || EMPTY_FORM)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setSaving(true)
    try {
      const data = {
        ...form,
        bedrooms:  form.bedrooms  ? parseInt(form.bedrooms)   : null,
        bathrooms: form.bathrooms ? parseFloat(form.bathrooms) : null,
        sqft:      form.sqft      ? parseInt(form.sqft)        : null,
        price:     form.price     ? parseFloat(form.price)     : null,
      }
      const saved = property?.id
        ? await api.updateProperty(property.id, data)
        : await api.createProperty(data)
      onSave(saved)
      onClose()
    } finally {
      setSaving(false)
    }
  }

  const field = (label, name, type = 'text', opts = {}) => (
    <div>
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      {opts.textarea ? (
        <textarea
          value={form[name] || ''}
          onChange={e => setForm({ ...form, [name]: e.target.value })}
          rows={3}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
        />
      ) : opts.select ? (
        <select
          value={form[name] || ''}
          onChange={e => setForm({ ...form, [name]: e.target.value })}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
        >
          {opts.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      ) : (
        <input
          type={type}
          value={form[name] || ''}
          onChange={e => setForm({ ...form, [name]: e.target.value })}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
        />
      )}
    </div>
  )

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-surface rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">
            {property?.id ? 'Edit Property' : 'Add Property'}
          </h2>
          <button onClick={onClose}><X className="w-5 h-5 text-gray-400" /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {field('Property Title *', 'title')}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {field('Address', 'address')}
            {field('City', 'city')}
            {field('State', 'state')}
            {field('ZIP', 'zip')}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {field('Type', 'property_type', 'text', { select: true, options: [
              { value: 'house', label: 'House' }, { value: 'condo', label: 'Condo' },
              { value: 'apartment', label: 'Apartment' }, { value: 'townhouse', label: 'Townhouse' },
              { value: 'land', label: 'Land' }, { value: 'commercial', label: 'Commercial' },
            ]})}
            {field('Status', 'status', 'text', { select: true, options: [
              { value: 'active', label: 'Active' }, { value: 'pending', label: 'Pending' },
              { value: 'sold', label: 'Sold' }, { value: 'off_market', label: 'Off Market' },
            ]})}
            {field('MLS #', 'mls_number')}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {field('Bedrooms', 'bedrooms', 'number')}
            {field('Bathrooms', 'bathrooms', 'number')}
            {field('Sqft', 'sqft', 'number')}
            {field('Price ($)', 'price', 'number')}
          </div>
          {field('Description', 'description', 'text', { textarea: true })}
          <div className="flex justify-end gap-3 pt-4">
            <button type="button" onClick={onClose} className="btn-secondary">Cancel</button>
            <button type="submit" disabled={saving} className="btn-primary">
              {saving ? 'Saving…' : 'Save Property'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function PropertyCard({ property, index, onEdit, onDelete }) {
  const features = Array.isArray(property.features) ? property.features : []
  const price = property.price ? `$${Number(property.price).toLocaleString()}` : null
  const desc = property.description?.slice(0, 100)

  return (
    <div className="bg-surface rounded-xl border border-gray-200 overflow-hidden hover:shadow-lg transition-shadow group">
      {/* Photo */}
      <div className="relative h-44 overflow-hidden bg-gray-100">
        <img
          src={photoUrl(index)}
          alt={property.title}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
          onError={e => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'flex' }}
        />
        <div className="w-full h-full bg-gradient-to-br from-navy-600 to-navy-800 items-center justify-center hidden">
          <Building2 className="w-8 h-8 text-white/30" />
        </div>

        {/* Status badge over image */}
        <div className="absolute top-3 left-3">
          <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border backdrop-blur-sm ${STATUS_COLORS[property.status] || 'bg-gray-100 text-gray-500'}`}>
            {property.status?.replace('_', ' ')}
          </span>
        </div>

        {/* Type badge */}
        <div className="absolute top-3 right-3">
          <span className="text-xs font-medium px-2 py-1 rounded-full bg-black/60 text-white backdrop-blur-sm">
            {TYPE_LABELS[property.property_type] || property.property_type}
          </span>
        </div>

        {/* Price overlay */}
        {price && (
          <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent px-4 py-3">
            <p className="text-white font-bold text-lg">{price}</p>
          </div>
        )}
      </div>

      {/* Body */}
      <div className="p-4">
        <h3 className="font-semibold text-gray-900 text-sm leading-snug mb-1">{property.title}</h3>

        {(property.city || property.state) && (
          <div className="flex items-center gap-1 text-xs text-gray-400 mb-3">
            <MapPin className="w-3 h-3" />
            {[property.address, property.city, property.state].filter(Boolean).join(', ')}
          </div>
        )}

        {/* Specs row */}
        <div className="flex items-center gap-3 text-xs text-gray-500 mb-3">
          {property.bedrooms && (
            <span className="flex items-center gap-1"><Bed className="w-3.5 h-3.5" />{property.bedrooms} bd</span>
          )}
          {property.bathrooms && (
            <span className="flex items-center gap-1"><Bath className="w-3.5 h-3.5" />{property.bathrooms} ba</span>
          )}
          {property.sqft && (
            <span className="flex items-center gap-1"><Maximize2 className="w-3.5 h-3.5" />{Number(property.sqft).toLocaleString()} ft²</span>
          )}
        </div>

        {/* Description excerpt */}
        {desc && (
          <p className="text-xs text-gray-400 leading-relaxed mb-3 line-clamp-2">{desc}…</p>
        )}

        {/* Feature pills */}
        {features.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3">
            {features.slice(0, 3).map((f, i) => (
              <span key={i} className="text-xs bg-gray-50 text-gray-500 border border-gray-100 px-2 py-0.5 rounded-full">
                {f}
              </span>
            ))}
            {features.length > 3 && (
              <span className="text-xs text-gray-400 px-1">+{features.length - 3} more</span>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between pt-3 border-t border-gray-50">
          {property.mls_number && (
            <span className="flex items-center gap-1 text-xs text-gray-400">
              <Tag className="w-3 h-3" />{property.mls_number}
            </span>
          )}
          <div className="flex gap-3 ml-auto">
            <button
              onClick={() => onEdit(property)}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-700 transition-colors"
            >
              <Pencil className="w-3.5 h-3.5" /> Edit
            </button>
            <button
              onClick={() => onDelete(property.id)}
              className="flex items-center gap-1 text-xs text-red-700 hover:text-red-800 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" /> Delete
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function Properties() {
  const [properties, setProperties] = useState([])
  const [modal, setModal] = useState(null)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    api.getProperties().then(setProperties).catch(console.error)
  }, [])

  async function handleDelete(id) {
    if (!confirm('Delete this property?')) return
    await api.deleteProperty(id)
    setProperties(prev => prev.filter(p => p.id !== id))
  }

  function handleSave(saved) {
    setProperties(prev => {
      const idx = prev.findIndex(p => p.id === saved.id)
      if (idx >= 0) { const next = [...prev]; next[idx] = saved; return next }
      return [saved, ...prev]
    })
  }

  const filtered = filter === 'all' ? properties : properties.filter(p => p.status === filter)
  const counts = {
    all: properties.length,
    active: properties.filter(p => p.status === 'active').length,
    pending: properties.filter(p => p.status === 'pending').length,
    sold: properties.filter(p => p.status === 'sold').length,
  }

  return (
    <div className="p-4 md:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Properties</h1>
          <p className="text-gray-500 text-sm mt-1">
            {counts.active} active · {counts.pending} pending · {counts.sold} sold · AI knowledge base synced
          </p>
        </div>
        <button onClick={() => setModal({})} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" /> Add Property
        </button>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-lg w-fit overflow-x-auto max-w-full">
        {['all', 'active', 'pending', 'sold'].map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium capitalize transition-colors ${
              filter === f ? 'bg-surface text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {f} <span className="text-xs opacity-60">({counts[f]})</span>
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="card text-center py-16">
          <Building2 className="w-10 h-10 text-gray-200 mx-auto mb-4" />
          <p className="text-gray-500 font-medium">No properties yet</p>
          <p className="text-gray-400 text-sm mt-1">Add a property and it will be automatically indexed for the AI</p>
          <button onClick={() => setModal({})} className="btn-primary mt-4">Add your first property</button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filtered.map((p, i) => (
            <PropertyCard
              key={p.id}
              property={p}
              index={i}
              onEdit={setModal}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      {modal !== null && (
        <PropertyModal
          property={modal?.id ? modal : null}
          onClose={() => setModal(null)}
          onSave={handleSave}
        />
      )}
    </div>
  )
}
