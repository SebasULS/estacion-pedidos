<template>
  <div id="app" v-cloak>
    <section v-if="!authReady" class="login-shell splash-screen">
      <div class="auth-card compact-auth">
        <div class="auth-logo">🍽️</div>
        <p class="eyebrow">Verificando sesión</p>
        <h1>Estación de Pedidos</h1>
        <p>Preparando OAuth y conexión con la API Flask...</p>
        <div class="auth-loader"></div>
      </div>
    </section>

    <section v-else-if="!currentUser" class="login-shell">
      <div class="auth-hero">
        <span class="tag">OAuth primero</span>
        <h1>Estación de Pedidos</h1>
        <p>Antes de ingresar al panel operativo, inicia sesión mediante OAuth o usa el token demo para la presentación.</p>
        <div class="auth-features">
          <div><strong>API REST protegida</strong><small>Bearer token para endpoints privados.</small></div>
          <div><strong>Keycloak OAuth 2.0</strong><small>Flujo web y flujo API disponibles.</small></div>
          <div><strong>Log NoSQL</strong><small>Eventos de autenticación registrados en JSONL.</small></div>
        </div>
      </div>

      <div class="auth-card">
        <div class="auth-logo">🔐</div>
        <p class="eyebrow">Acceso al sistema</p>
        <h2>Iniciar sesión</h2>
        <p class="muted">El panel de Menú, Pedidos, Inventario, Reportes y CRUD se habilita después de autenticarte.</p>

        <div class="auth-status">
          <span :class="['pill', apiOnline ? 'ok' : 'error']">{{ apiOnline ? 'API conectada' : 'API sin conexión' }}</span>
          <span :class="['pill', authConfig && authConfig.oauth_keycloak_configurado ? 'ok' : 'warning']">
            {{ authConfig && authConfig.oauth_keycloak_configurado ? 'Keycloak OAuth configurado' : 'Keycloak OAuth no configurado' }}
          </span>
        </div>

        <button class="btn primary full auth-main-btn" @click="keycloakLogin" :disabled="loading">
          Continuar con Keycloak
        </button>
        <button class="btn outline full" @click="demoLogin" :disabled="loading">
          Usar token demo API
        </button>

        <div class="auth-note">
          <strong>Endpoint OAuth:</strong>
          <code>GET /api/auth/oauth/keycloak/login</code>
          <strong>Endpoint demo:</strong>
          <code>POST /api/auth/demo-login</code>
        </div>
      </div>
    </section>

    <template v-else>
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-icon">🍽️</div>
        <div>
          <h1>Estación de Pedidos</h1>
          <p>Frontend Vue.js + Backend Flask</p>
        </div>
      </div>

      <nav class="nav-menu">
        <button v-for="item in navItems" :key="item.view" :class="['nav-item', { active: view === item.view }]" @click="setView(item.view)">
          <span>{{ item.icon }}</span>
          <strong>{{ item.label }}</strong>
        </button>
      </nav>

      <section class="session-card">
        <div class="pill" :class="apiOnline ? 'ok' : 'error'">
          {{ apiOnline ? 'API conectada' : 'API sin conexión' }}
        </div>
        <div class="user-mini" v-if="currentUser">
          <img v-if="currentUser.avatar_url" :src="currentUser.avatar_url" alt="Avatar" />
          <div>
            <strong>{{ currentUser.nombre }}</strong>
            <small>{{ currentUser.email }}</small>
          </div>
        </div>
        <p v-else class="muted small">Sesión de invitado. Puedes usar token demo para endpoints protegidos.</p>
        <div class="session-actions">
          <button class="btn ghost small" @click="demoLogin">Token demo</button>
          <button class="btn ghost small" @click="keycloakLogin">OAuth Keycloak</button>
          <button class="btn ghost small" @click="logout">Salir</button>
        </div>
      </section>
    </aside>

    <main class="main">
      <header class="topbar">
        <div>
          <p class="eyebrow">Sistema de gestión para restaurante</p>
          <h2>{{ activeTitle }}</h2>
        </div>
        <div class="top-actions">
          <button class="btn ghost" @click="refreshCurrent">↻ Actualizar</button>
          <a class="btn outline" :href="API + '/health'" target="_blank">API Health</a>
        </div>
      </header>

      <section v-if="view === 'dashboard'" class="view">
        <div class="hero-card">
          <div>
            <span class="tag">Vue.js integrado</span>
            <h3>Panel operativo de Estación de Pedidos</h3>
            <p>Gestiona pedidos, productos, inventario, pagos, reportes, OAuth y trabajos futuros desde una SPA simple servida por Flask.</p>
          </div>
          <button class="btn primary" @click="setView('mozo')">Tomar pedido</button>
        </div>

        <div class="stats-grid">
          <article class="stat-card">
            <span>Ventas totales</span>
            <strong>{{ money(reports.ventas.ventas_totales) }}</strong>
            <small>Transacciones pagadas</small>
          </article>
          <article class="stat-card">
            <span>Ticket promedio</span>
            <strong>{{ money(reports.ventas.ticket_promedio) }}</strong>
            <small>Promedio por venta</small>
          </article>
          <article class="stat-card">
            <span>Fondo social</span>
            <strong>{{ money(reports.ventas.aporte_ollas_comunes) }}</strong>
            <small>Ollas comunes</small>
          </article>
          <article class="stat-card warning">
            <span>Stock bajo</span>
            <strong>{{ reports.stockBajo.length }}</strong>
            <small>Productos por revisar</small>
          </article>
        </div>

        <div class="grid two">
          <section class="card">
            <div class="card-title">
              <h3>Últimos pedidos</h3>
              <button class="btn ghost small" @click="setView('pedidos')">Ver historial</button>
            </div>
            <div class="list compact">
              <div v-for="o in orders.slice(0, 6)" :key="o.id_pedido" class="list-row">
                <div>
                  <strong>Pedido #{{ o.id_pedido }}</strong>
                  <small>{{ o.creado_en }} · Mesa {{ o.id_mesa || 'S/M' }}</small>
                </div>
                <div class="right">
                  <span :class="['badge', statusClass(o.estado)]">{{ o.estado }}</span>
                  <strong>{{ money(o.total) }}</strong>
                </div>
              </div>
              <p v-if="!orders.length" class="empty">Aún no hay pedidos registrados.</p>
            </div>
          </section>

          <section class="card">
            <div class="card-title">
              <h3>Productos con stock bajo</h3>
              <button class="btn ghost small" @click="setView('inventario')">Ir a inventario</button>
            </div>
            <div class="list compact">
              <div v-for="p in reports.stockBajo.slice(0, 6)" :key="p.id_producto" class="list-row">
                <div>
                  <strong>{{ p.nombre }}</strong>
                  <small>Mínimo: {{ p.stock_minimo }} {{ p.unidad_medida }}</small>
                </div>
                <div class="right">
                  <span class="badge danger">{{ p.estado_stock }}</span>
                  <strong>{{ p.stock_actual }}</strong>
                </div>
              </div>
              <p v-if="!reports.stockBajo.length" class="empty">No hay alertas de stock bajo.</p>
            </div>
          </section>
        </div>
      </section>

      <section v-if="view === 'mozo'" class="view">
        <div class="grid mozo-layout">
          <section class="card menu-card">
            <div class="card-title">
              <div>
                <h3>Catálogo visual</h3>
                <p class="muted">Busca productos disponibles y agrégalos al pedido.</p>
              </div>
              <span class="pill">{{ shownProducts.length }} productos</span>
            </div>

            <div class="toolbar">
              <input v-model.trim="productSearch" @input="searchProductsDebounced" type="search" placeholder="Buscar por nombre, categoría o descripción..." />
              <select v-model="categoryFilter">
                <option value="">Todas las categorías</option>
                <option v-for="c in categories" :key="c.id_categoria" :value="c.id_categoria">{{ c.nombre }}</option>
              </select>
            </div>

            <div class="products-grid">
              <article v-for="p in shownProducts" :key="p.id_producto" class="product-card">
                <div class="product-img" :style="{ backgroundImage: `url(${p.imagen_url || fallbackImage})` }"></div>
                <div class="product-body">
                  <div>
                    <h4>{{ p.nombre }}</h4>
                    <p>{{ p.descripcion || 'Producto disponible' }}</p>
                  </div>
                  <div class="product-meta">
                    <strong>{{ money(p.precio) }}</strong>
                    <span :class="['stock-chip', Number(p.stock_actual) <= Number(p.stock_minimo || 5) ? 'low' : '']">Stock: {{ p.stock_actual ?? '-' }}</span>
                  </div>
                  <button class="btn primary full" @click="addToCart(p)">+ Añadir</button>
                </div>
              </article>
              <p v-if="!shownProducts.length" class="empty wide">No se encontraron productos disponibles.</p>
            </div>
          </section>

          <aside class="card order-panel">
            <div class="card-title">
              <h3>Pedido actual</h3>
              <button class="btn ghost small" @click="clearCart">Limpiar</button>
            </div>

            <label>Mesa</label>
            <select v-model="orderForm.id_mesa">
              <option :value="null">Sin mesa</option>
              <option v-for="m in availableTables" :key="m.id_mesa" :value="m.id_mesa">{{ m.codigo }} · cap. {{ m.capacidad }}</option>
            </select>

            <label>Comentario del pedido</label>
            <textarea v-model="orderForm.comentario" rows="3" placeholder="Ej. sin cebolla, urgente, entregar en barra..."></textarea>

            <div class="cart-list">
              <div v-for="item in cart" :key="item.id_producto" class="cart-row">
                <div>
                  <strong>{{ item.nombre }}</strong>
                  <small>{{ money(item.precio) }} c/u · stock {{ item.stock_actual }}</small>
                </div>
                <div class="qty">
                  <button @click="changeQty(item.id_producto, -1)">−</button>
                  <span>{{ item.cantidad }}</span>
                  <button @click="changeQty(item.id_producto, 1)">+</button>
                  <button class="danger-btn" @click="removeFromCart(item.id_producto)">×</button>
                </div>
              </div>
              <p v-if="!cart.length" class="empty">Agrega productos para iniciar el pedido.</p>
            </div>

            <div class="total-box">
              <span>Total</span>
              <strong>{{ money(cartTotal) }}</strong>
            </div>
            <button class="btn primary full" :disabled="!cart.length || loading" @click="createOrder">Registrar pedido</button>
          </aside>
        </div>
      </section>

      <section v-if="view === 'pedidos'" class="view">
        <section class="card">
          <div class="card-title">
            <div>
              <h3>Historial y control de estados</h3>
              <p class="muted">Consulta pedidos, cambia estados y revisa auditoría.</p>
            </div>
            <div class="toolbar small-toolbar">
              <select v-model="orderStatusFilter">
                <option value="">Todos</option>
                <option value="registrado">Registrado</option>
                <option value="en_preparacion">En preparación</option>
                <option value="entregado">Entregado</option>
                <option value="pagado">Pagado</option>
                <option value="cancelado">Cancelado</option>
              </select>
            </div>
          </div>

          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th><th>Mesa</th><th>Estado</th><th>Total</th><th>Fecha</th><th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="o in filteredOrders" :key="o.id_pedido">
                  <td>#{{ o.id_pedido }}</td>
                  <td>{{ o.id_mesa || 'S/M' }}</td>
                  <td><span :class="['badge', statusClass(o.estado)]">{{ o.estado }}</span></td>
                  <td>{{ money(o.total) }}</td>
                  <td>{{ o.creado_en }}</td>
                  <td class="actions-cell">
                    <select v-model="o._nextEstado">
                      <option value="registrado">registrado</option>
                      <option value="en_preparacion">en_preparacion</option>
                      <option value="entregado">entregado</option>
                      <option value="pagado">pagado</option>
                      <option value="cancelado">cancelado</option>
                    </select>
                    <button class="btn ghost small" @click="updateOrderStatus(o)">Guardar</button>
                    <button class="btn outline small" @click="loadAudit(o.id_pedido)">Auditoría</button>
                  </td>
                </tr>
              </tbody>
            </table>
            <p v-if="!filteredOrders.length" class="empty">No hay pedidos con el filtro seleccionado.</p>
          </div>
        </section>

        <section v-if="audit" class="card json-card">
          <div class="card-title">
            <h3>Auditoría del pedido #{{ audit.pedido?.id_pedido }}</h3>
            <button class="btn ghost small" @click="audit = null">Cerrar</button>
          </div>
          <pre>{{ pretty(audit) }}</pre>
        </section>
      </section>

      <section v-if="view === 'inventario'" class="view">
        <div class="grid two">
          <section class="card">
            <div class="card-title">
              <h3>Stock actual</h3>
              <span class="pill">{{ inventory.length }} registros</span>
            </div>
            <div class="list">
              <div v-for="i in inventoryWithProducts" :key="i.id_inventario" class="inventory-row">
                <div>
                  <strong>{{ i.producto_nombre }}</strong>
                  <small>{{ i.unidad_medida }} · actualizado {{ i.actualizado_en }}</small>
                </div>
                <div class="right">
                  <span :class="['badge', Number(i.stock_actual) <= Number(i.stock_minimo || 5) ? 'danger' : 'success']">
                    {{ Number(i.stock_actual) <= Number(i.stock_minimo || 5) ? 'stock bajo' : 'ok' }}
                  </span>
                  <strong>{{ i.stock_actual }}</strong>
                </div>
              </div>
            </div>
          </section>

          <section class="card">
            <h3>Ajuste de inventario</h3>
            <label>Producto</label>
            <select v-model="inventoryForm.id_producto">
              <option :value="null">Seleccionar producto</option>
              <option v-for="p in products" :key="p.id_producto" :value="p.id_producto">{{ p.nombre }}</option>
            </select>

            <label>Tipo de movimiento</label>
            <select v-model="inventoryForm.tipo_movimiento">
              <option value="entrada">Entrada</option>
              <option value="salida">Salida</option>
              <option value="ajuste">Ajuste</option>
            </select>

            <label>Cantidad</label>
            <input type="number" min="1" v-model.number="inventoryForm.cantidad" />

            <label>Motivo</label>
            <input type="text" v-model="inventoryForm.motivo" placeholder="Ej. compra a proveedor" />

            <button class="btn primary full" @click="adjustInventory">Aplicar ajuste</button>
          </section>
        </div>

        <section class="card">
          <div class="card-title"><h3>Movimientos de inventario</h3></div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>ID</th><th>Producto</th><th>Tipo</th><th>Cantidad</th><th>Anterior</th><th>Nuevo</th><th>Motivo</th></tr></thead>
              <tbody>
                <tr v-for="m in inventoryMovements" :key="m.id_movimiento">
                  <td>{{ m.id_movimiento }}</td>
                  <td>{{ productName(m.id_producto) }}</td>
                  <td><span class="badge neutral">{{ m.tipo_movimiento }}</span></td>
                  <td>{{ m.cantidad }}</td>
                  <td>{{ m.stock_anterior }}</td>
                  <td>{{ m.stock_nuevo }}</td>
                  <td>{{ m.motivo }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </section>

      <section v-if="view === 'pagos'" class="view">
        <div class="grid two">
          <section class="card">
            <h3>Confirmar pago</h3>
            <label>ID de pedido</label>
            <input type="number" min="1" v-model.number="paymentForm.id_pedido" placeholder="Ej. 3" />
            <label>Método de pago</label>
            <select v-model="paymentForm.metodo_pago">
              <option value="efectivo">Efectivo</option>
              <option value="yape">Yape</option>
              <option value="plin">Plin</option>
              <option value="tarjeta">Tarjeta</option>
              <option value="transferencia">Transferencia</option>
            </select>
            <label>Referencia</label>
            <input v-model="paymentForm.referencia" placeholder="Nro. operación o código" />
            <button class="btn primary full" @click="confirmPayment">Confirmar pago</button>
          </section>

          <section class="card">
            <div class="card-title"><h3>Últimas transacciones</h3><span class="pill">{{ transactions.length }}</span></div>
            <div class="list compact">
              <div v-for="t in transactions" :key="t.id_transaccion" class="list-row">
                <div>
                  <strong>Pedido #{{ t.id_pedido }}</strong>
                  <small>{{ t.metodo_pago }} · {{ t.fecha }}</small>
                </div>
                <div class="right">
                  <span :class="['badge', t.estado === 'pagado' ? 'success' : 'neutral']">{{ t.estado }}</span>
                  <strong>{{ money(t.monto) }}</strong>
                </div>
              </div>
              <p v-if="!transactions.length" class="empty">Aún no hay transacciones.</p>
            </div>
          </section>
        </div>
      </section>

      <section v-if="view === 'reportes'" class="view">
        <section class="card">
          <div class="card-title">
            <div>
              <h3>Indicadores operativos</h3>
              <p class="muted">Reportes funcionales desarrollados en el backend Flask.</p>
            </div>
            <div class="toolbar small-toolbar">
              <input type="date" v-model="reportFilters.desde" />
              <input type="date" v-model="reportFilters.hasta" />
              <button class="btn ghost small" @click="loadReports">Filtrar</button>
            </div>
          </div>
          <div class="stats-grid">
            <article class="stat-card"><span>Ventas totales</span><strong>{{ money(reports.ventas.ventas_totales) }}</strong></article>
            <article class="stat-card"><span>Ticket promedio</span><strong>{{ money(reports.ventas.ticket_promedio) }}</strong></article>
            <article class="stat-card"><span>Transacciones</span><strong>{{ reports.ventas.transacciones_pagadas || 0 }}</strong></article>
            <article class="stat-card"><span>Aporte social</span><strong>{{ money(reports.ventas.aporte_ollas_comunes) }}</strong></article>
          </div>
        </section>

        <div class="grid two">
          <section class="card">
            <h3>Productos más vendidos</h3>
            <div class="list compact">
              <div v-for="p in reports.topProducts" :key="p.id_producto" class="list-row">
                <div><strong>{{ p.nombre }}</strong><small>{{ p.cantidad_vendida }} unidades</small></div>
                <strong>{{ money(p.ingreso_generado) }}</strong>
              </div>
              <p v-if="!reports.topProducts.length" class="empty">No hay ventas para calcular ranking.</p>
            </div>
          </section>
          <section class="card">
            <h3>Pedidos por estado</h3>
            <div class="list compact">
              <div v-for="e in reports.ordersByStatus" :key="e.estado" class="list-row">
                <div><strong>{{ e.estado }}</strong><small>{{ e.total_pedidos }} pedidos</small></div>
                <strong>{{ money(e.monto_total) }}</strong>
              </div>
            </div>
          </section>
        </div>

        <section class="card">
          <h3>Stock bajo o agotado</h3>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Producto</th><th>Stock actual</th><th>Mínimo</th><th>Unidad</th><th>Estado</th></tr></thead>
              <tbody>
                <tr v-for="s in reports.stockBajo" :key="s.id_producto">
                  <td>{{ s.nombre }}</td><td>{{ s.stock_actual }}</td><td>{{ s.stock_minimo }}</td><td>{{ s.unidad_medida }}</td><td><span class="badge danger">{{ s.estado_stock }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </section>


      <section v-if="view === 'facturacion'" class="view">
        <section class="card">
          <div class="card-title">
            <div>
              <h3>Facturación electrónica SUNAT</h3>
              <p class="muted">Emisión de boletas y facturas mediante API REST con credenciales <strong>personalId</strong> + <strong>personaToken</strong>.</p>
            </div>
            <button class="btn ghost small" @click="loadSunatModule">Actualizar</button>
          </div>

          <div class="stats-grid">
            <article class="stat-card">
              <span>Ambiente</span>
              <strong>{{ sunatConfig ? sunatConfig.ambiente : '-' }}</strong>
              <small>{{ sunatConfig && sunatConfig.modo_real ? 'Modo real API' : 'Modo desarrollo/simulado' }}</small>
            </article>
            <article class="stat-card" :class="sunatConfig && sunatConfig.configurado ? '' : 'warning'">
              <span>Credenciales API</span>
              <strong>{{ sunatConfig && sunatConfig.configurado ? 'Configuradas' : 'Pendientes' }}</strong>
              <small>personalId + personaToken desde .env</small>
            </article>
            <article class="stat-card">
              <span>Serie boleta</span>
              <strong>{{ sunatConfig ? sunatConfig.serie_boleta : 'B001' }}</strong>
              <small>Comprobante 03</small>
            </article>
            <article class="stat-card">
              <span>Serie factura</span>
              <strong>{{ sunatConfig ? sunatConfig.serie_factura : 'F001' }}</strong>
              <small>Comprobante 01</small>
            </article>
          </div>
        </section>

        <div class="grid two">
          <section class="card">
            <h3>Emitir desde pedido</h3>
            <p class="muted">Selecciona un pedido registrado o pagado. El backend toma sus detalles, total y productos para generar el payload SUNAT.</p>
            <label>Pedido</label>
            <select v-model.number="sunatForm.id_pedido">
              <option :value="null">Seleccionar pedido</option>
              <option v-for="o in paidOrdersForSunat()" :key="o.id_pedido" :value="o.id_pedido">#{{ o.id_pedido }} · {{ o.estado }} · {{ money(o.total) }}</option>
            </select>
            <label>Tipo de comprobante</label>
            <select v-model="sunatForm.tipo_comprobante">
              <option value="boleta">Boleta electrónica</option>
              <option value="factura">Factura electrónica</option>
            </select>
            <div class="grid two mini-grid">
              <div>
                <label>Tipo doc. cliente</label>
                <select v-model="sunatForm.cliente.tipo_documento">
                  <option value="1">DNI</option>
                  <option value="6">RUC</option>
                  <option value="0">Sin documento</option>
                </select>
              </div>
              <div>
                <label>Número doc.</label>
                <input v-model="sunatForm.cliente.numero_documento" placeholder="DNI o RUC" />
              </div>
            </div>
            <label>Cliente / razón social</label>
            <input v-model="sunatForm.cliente.nombre" placeholder="Cliente varios" />
            <label>Dirección</label>
            <input v-model="sunatForm.cliente.direccion" placeholder="Dirección fiscal o comercial" />
            <button class="btn primary full" @click="emitSunatFromPedido">Emitir comprobante SUNAT</button>
          </section>

          <section class="card">
            <h3>Emitir comprobante manual</h3>
            <p class="muted">Útil para Postman o pruebas rápidas sin depender de un pedido existente.</p>
            <textarea v-model="sunatForm.manualJson" rows="15"></textarea>
            <button class="btn outline full" @click="emitSunatManual">POST /api/sunat/comprobantes</button>
          </section>
        </div>

        <section class="card">
          <div class="card-title">
            <div>
              <h3>Comprobantes registrados</h3>
              <p class="muted">Los documentos emitidos se guardan en SQL; los eventos operativos se registran en el log NoSQL JSONL.</p>
            </div>
            <span class="pill">{{ comprobantes.length }} documentos</span>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr><th>ID</th><th>Pedido</th><th>Tipo</th><th>Serie</th><th>Número</th><th>Cliente</th><th>Total</th><th>Estado SUNAT</th><th>Acciones</th></tr>
              </thead>
              <tbody>
                <tr v-for="c in comprobantes" :key="c.id_comprobante">
                  <td>{{ c.id_comprobante }}</td>
                  <td>{{ c.id_pedido || '-' }}</td>
                  <td>{{ c.tipo_comprobante }}</td>
                  <td>{{ c.serie }}</td>
                  <td>{{ c.numero }}</td>
                  <td>{{ c.cliente_nombre }}</td>
                  <td>{{ money(c.total) }}</td>
                  <td><span :class="['badge', String(c.estado_sunat).includes('ANUL') ? 'danger' : 'success']">{{ c.estado_sunat }}</span></td>
                  <td class="actions-cell">
                    <button class="btn ghost small" @click="consultSunatDoc(c)">Consultar</button>
                    <button class="btn ghost small danger-text" @click="cancelSunatDoc(c)">Anular</button>
                  </td>
                </tr>
              </tbody>
            </table>
            <p v-if="!comprobantes.length" class="empty">Aún no se emitieron comprobantes electrónicos.</p>
          </div>
        </section>

        <section v-if="integrationResult" class="card json-card">
          <div class="card-title"><h3>Respuesta API SUNAT</h3><button class="btn ghost small" @click="integrationResult = null">Cerrar</button></div>
          <pre>{{ pretty(integrationResult) }}</pre>
        </section>
      </section>

      <section v-if="view === 'integraciones'" class="view">
        <section class="card">
          <div class="card-title">
            <div>
              <h3>Trabajos futuros e integraciones API</h3>
              <p class="muted">Módulo preparado para SUNAT, PedidosYa, Rappi y contabilidad.</p>
            </div>
            <button class="btn ghost small" @click="loadFutureWork">Actualizar</button>
          </div>
          <div class="future-grid">
            <article v-for="f in futureWork" :key="f.nombre" class="future-card">
              <span class="badge neutral">{{ f.estado }}</span>
              <h4>{{ f.nombre }}</h4>
              <p>{{ f.objetivo }}</p>
              <code>{{ f.endpoint }}</code>
              <button class="btn outline full" @click="simulateFuture(f)">Simular API</button>
            </article>
          </div>
        </section>

        <div class="grid two">
          <section class="card">
            <h3>Consulta SUNAT simulada</h3>
            <label>RUC</label>
            <input v-model="sunatForm.ruc" placeholder="Ej. 20123456789" />
            <button class="btn primary full" @click="consultRuc">Consultar RUC</button>
          </section>
          <section class="card">
            <h3>PedidosYa simulado</h3>
            <p class="muted">Endpoint de integración para delivery externo.</p>
            <button class="btn primary full" @click="createPedidosYa">Generar pedido externo</button>
          </section>
        </div>

        <section v-if="integrationResult" class="card json-card">
          <div class="card-title"><h3>Resultado de integración</h3><button class="btn ghost small" @click="integrationResult = null">Cerrar</button></div>
          <pre>{{ pretty(integrationResult) }}</pre>
        </section>
      </section>

      <section v-if="view === 'crud'" class="view">
        <section class="card">
          <div class="card-title">
            <div>
              <h3>CRUD genérico de tablas</h3>
              <p class="muted">Todas las tablas tienen endpoints REST para listar, crear, actualizar y eliminar.</p>
            </div>
            <div class="toolbar small-toolbar">
              <select v-model="crud.table" @change="loadCrudTable">
                <option v-for="t in crudTables" :key="t" :value="t">{{ t }}</option>
              </select>
              <button class="btn ghost small" @click="loadCrudTable">Listar</button>
            </div>
          </div>

          <div class="grid two">
            <div class="json-card flat">
              <h4>Crear registro</h4>
              <textarea v-model="crud.createJson" rows="9"></textarea>
              <button class="btn primary full" @click="createCrudRecord">POST /api/{{ crud.table }}</button>
            </div>
            <div class="json-card flat">
              <h4>Actualizar registro</h4>
              <input type="number" v-model.number="crud.updateId" placeholder="ID del registro" />
              <textarea v-model="crud.updateJson" rows="7"></textarea>
              <button class="btn outline full" @click="updateCrudRecord">PATCH /api/{{ crud.table }}/{{ crud.updateId || ':id' }}</button>
            </div>
          </div>

          <div class="table-wrap">
            <table>
              <thead><tr><th v-for="h in crudHeaders" :key="h">{{ h }}</th><th>Acción</th></tr></thead>
              <tbody>
                <tr v-for="row in crud.rows" :key="crudRowKey(row)">
                  <td v-for="h in crudHeaders" :key="h">{{ row[h] }}</td>
                  <td><button class="btn ghost small danger-text" @click="deleteCrudRecord(row)">Eliminar</button></td>
                </tr>
              </tbody>
            </table>
            <p v-if="!crud.rows.length" class="empty">No hay registros para mostrar.</p>
          </div>
        </section>
      </section>

      <section v-if="view === 'logs'" class="view">
        <section class="card">
          <div class="card-title"><h3>Log NoSQL JSONL</h3><button class="btn ghost small" @click="loadLogs">Actualizar</button></div>
          <div class="json-card flat"><pre>{{ pretty(logs) }}</pre></div>
        </section>
      </section>
    </main>

    </template>

    <div class="toast" :class="{ show: toast.show, error: toast.type === 'error' }">{{ toast.message }}</div>
    <div class="loading" v-if="loading"><span></span> Procesando...</div>
  </div>
</template>

<script>
import { API_BASE } from './config'

export default {
  name: 'App',
  data() {
    return {
      API: API_BASE,
      authReady: false,
      authConfig: null,
      view: 'dashboard',
      loading: false,
      apiOnline: false,
      fallbackImage: 'https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=700&auto=format&fit=crop',
      navItems: [
        { view: 'dashboard', label: 'Dashboard', icon: '📊' },
        { view: 'mozo', label: 'Mozo', icon: '🧑‍🍳' },
        { view: 'pedidos', label: 'Pedidos', icon: '📋' },
        { view: 'inventario', label: 'Inventario', icon: '📦' },
        { view: 'pagos', label: 'Pagos', icon: '🧾' },
        { view: 'reportes', label: 'Reportes', icon: '📈' },
        { view: 'facturacion', label: 'Facturación SUNAT', icon: '🧾' },
        { view: 'integraciones', label: 'Integraciones', icon: '🔗' },
        { view: 'crud', label: 'CRUD API', icon: '🧩' },
        { view: 'logs', label: 'Logs NoSQL', icon: '🪵' },
      ],
      products: [],
      availableProducts: [],
      categories: [],
      mesas: [],
      cart: [],
      productSearch: '',
      categoryFilter: '',
      searchTimer: null,
      orderForm: {
        id_mesa: null,
        comentario: '',
      },
      orders: [],
      orderStatusFilter: '',
      audit: null,
      inventory: [],
      inventoryMovements: [],
      inventoryForm: {
        id_producto: null,
        tipo_movimiento: 'entrada',
        cantidad: 1,
        motivo: 'Ajuste manual',
      },
      transactions: [],
      paymentForm: {
        id_pedido: null,
        metodo_pago: 'efectivo',
        referencia: '',
      },
      reports: {
        ventas: {},
        topProducts: [],
        stockBajo: [],
        ordersByStatus: [],
        fondoSocial: {},
      },
      reportFilters: {
        desde: '',
        hasta: '',
      },
      futureWork: [],
      integrationResult: null,
      sunatConfig: null,
      comprobantes: [],
      sunatForm: {
        ruc: '20123456789',
        id_pedido: null,
        tipo_comprobante: 'boleta',
        cliente: {
          tipo_documento: '1',
          numero_documento: '00000000',
          nombre: 'Cliente varios',
          direccion: 'Arequipa - Perú',
          email: '',
        },
        manualJson: '{\n  "tipo_comprobante": "boleta",\n  "cliente": {\n    "tipo_documento": "1",\n    "numero_documento": "00000000",\n    "nombre": "Cliente varios",\n    "direccion": "Arequipa - Perú"\n  },\n  "items": [\n    { "descripcion": "Menú demo", "cantidad": 1, "precio_unitario": 12, "subtotal": 12 }\n  ],\n  "subtotal": 12,\n  "igv": 0,\n  "total": 12\n}',
      },
      crudTables: [
        'roles', 'usuarios', 'oauth_cuentas', 'sesiones_api', 'categorias', 'mesas', 'productos', 'inventario',
        'pedidos', 'pedido_detalles', 'transacciones', 'inventario_movimientos', 'fondos_sociales', 'comprobantes_electronicos', 'integraciones'
      ],
      crudPk: {
        roles: 'id_rol', usuarios: 'id_usuario', oauth_cuentas: 'id_oauth', sesiones_api: 'id_sesion', categorias: 'id_categoria', mesas: 'id_mesa', productos: 'id_producto', inventario: 'id_inventario', pedidos: 'id_pedido', pedido_detalles: 'id_detalle', transacciones: 'id_transaccion', inventario_movimientos: 'id_movimiento', fondos_sociales: 'id_fondo', comprobantes_electronicos: 'id_comprobante', integraciones: 'id_integracion'
      },
      crudExamples: {
        roles: '{\n  "nombre": "cajero",\n  "descripcion": "Responsable de caja"\n}',
        usuarios: '{\n  "nombre": "Usuario Demo",\n  "email": "demo2@local.test",\n  "password_hash": "demo",\n  "id_rol": 1,\n  "activo": 1\n}',
        oauth_cuentas: '{\n  "id_usuario": 1,\n  "proveedor": "keycloak",\n  "proveedor_user_id": "demo-keycloak-id",\n  "email": "demo.keycloak@test.com",\n  "nombre": "OAuth Demo"\n}',
        sesiones_api: '{\n  "id_usuario": 1,\n  "jti": "manual-session-demo",\n  "proveedor": "demo",\n  "expira_en": "2099-01-01 00:00:00"\n}',
        categorias: '{\n  "nombre": "Bebidas calientes",\n  "descripcion": "Infusiones y cafés",\n  "activo": 1\n}',
        mesas: '{\n  "codigo": "M-09",\n  "capacidad": 4,\n  "estado": "disponible"\n}',
        productos: '{\n  "id_categoria": 1,\n  "nombre": "Producto demo",\n  "descripcion": "Creado desde Vue",\n  "precio": 9.90,\n  "stock_minimo": 5,\n  "activo": 1\n}',
        inventario: '{\n  "id_producto": 1,\n  "stock_actual": 20,\n  "unidad_medida": "unidad"\n}',
        pedidos: '{\n  "id_usuario": 1,\n  "estado": "registrado",\n  "comentario": "Pedido creado por CRUD",\n  "subtotal": 0,\n  "impuesto": 0,\n  "descuento": 0,\n  "total": 0\n}',
        pedido_detalles: '{\n  "id_pedido": 1,\n  "id_producto": 1,\n  "cantidad": 1,\n  "precio_unitario": 10,\n  "subtotal": 10\n}',
        transacciones: '{\n  "id_pedido": 1,\n  "metodo_pago": "efectivo",\n  "monto": 10,\n  "estado": "pagado"\n}',
        inventario_movimientos: '{\n  "id_producto": 1,\n  "tipo_movimiento": "entrada",\n  "cantidad": 5,\n  "stock_anterior": 10,\n  "stock_nuevo": 15,\n  "motivo": "Registro manual"\n}',
        fondos_sociales: '{\n  "id_pedido": 1,\n  "porcentaje": 5,\n  "monto_base": 10,\n  "monto_aporte": 0.5,\n  "destino": "Ollas comunes"\n}',
        comprobantes_electronicos: '{\n  "tipo_comprobante": "boleta",\n  "codigo_tipo_comprobante": "03",\n  "serie": "B001",\n  "numero": "000001",\n  "cliente_tipo_documento": "1",\n  "cliente_nombre": "Cliente varios",\n  "subtotal": 12,\n  "igv": 0,\n  "total": 12,\n  "payload_json": "{}"\n}',
        integraciones: '{\n  "nombre": "API contable demo",\n  "tipo": "contabilidad",\n  "endpoint_base": "https://api.demo.local",\n  "estado": "planificado"\n}'
      },
      crud: {
        table: 'productos',
        rows: [],
        createJson: '',
        updateId: null,
        updateJson: '{\n  "activo": 1\n}',
      },
      logs: [],
      currentUser: null,
      toast: {
        show: false,
        type: 'ok',
        message: '',
      },
    };
  },

  computed: {
    activeTitle() {
      const item = this.navItems.find(i => i.view === this.view);
      return item ? `${item.icon} ${item.label}` : 'Estación de Pedidos';
    },
    cartTotal() {
      return this.cart.reduce((sum, item) => sum + Number(item.precio || 0) * Number(item.cantidad || 0), 0);
    },
    availableTables() {
      return this.mesas.filter(m => m.estado === 'disponible');
    },
    shownProducts() {
      let list = this.availableProducts;
      if (this.categoryFilter) {
        list = list.filter(p => Number(p.id_categoria) === Number(this.categoryFilter));
      }
      return list;
    },
    filteredOrders() {
      return this.orderStatusFilter
        ? this.orders.filter(o => o.estado === this.orderStatusFilter)
        : this.orders;
    },
    inventoryWithProducts() {
      return this.inventory.map(i => {
        const product = this.products.find(p => Number(p.id_producto) === Number(i.id_producto)) || {};
        return {
          ...i,
          producto_nombre: product.nombre || `Producto #${i.id_producto}`,
          stock_minimo: product.stock_minimo ?? 5,
        };
      });
    },
    crudHeaders() {
      const first = this.crud.rows[0];
      return first ? Object.keys(first) : [];
    },
  },

  async mounted() {
    this.restoreTokenFromHash();
    this.crud.createJson = this.crudExamples[this.crud.table];
    try {
      await this.checkHealth();
      await this.loadAuthConfig();
      await this.getMe(false);
      if (this.currentUser) {
        await this.loadInitialData();
      }
    } finally {
      this.authReady = true;
    }
  },

  methods: {
    async api(path, options = {}) {
      const token = localStorage.getItem('api_token');
      const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      };
      if (token) headers.Authorization = `Bearer ${token}`;

      const response = await fetch(`${this.API}${path}`, {
        ...options,
        headers,
      });

      const text = await response.text();
      let data = null;
      try {
        data = text ? JSON.parse(text) : {};
      } catch (_) {
        data = { raw: text };
      }

      if (!response.ok) {
        const detail = data.detail || data.message || data.error || `Error HTTP ${response.status}`;
        throw new Error(detail);
      }
      return data;
    },

    async withLoading(callback) {
      this.loading = true;
      try {
        return await callback();
      } finally {
        this.loading = false;
      }
    },

    notify(message, type = 'ok') {
      this.toast = { show: true, type, message };
      window.clearTimeout(this._toastTimer);
      this._toastTimer = window.setTimeout(() => {
        this.toast.show = false;
      }, 3200);
    },

    money(value) {
      return `S/ ${Number(value || 0).toFixed(2)}`;
    },

    pretty(value) {
      return JSON.stringify(value, null, 2);
    },

    statusClass(status) {
      return {
        registrado: 'neutral',
        en_preparacion: 'warning',
        entregado: 'info',
        pagado: 'success',
        cancelado: 'danger',
      }[status] || 'neutral';
    },

    productName(id_producto) {
      const p = this.products.find(x => Number(x.id_producto) === Number(id_producto));
      return p ? p.nombre : `Producto #${id_producto}`;
    },

    async checkHealth() {
      try {
        await this.api('/health');
        this.apiOnline = true;
      } catch (_) {
        this.apiOnline = false;
      }
    },

    async loadAuthConfig() {
      try {
        this.authConfig = await this.api('/auth/config');
      } catch (_) {
        this.authConfig = null;
      }
    },

    async loadInitialData() {
      await this.withLoading(async () => {
        await Promise.allSettled([
          this.loadProducts(),
          this.loadCategories(),
          this.loadTables(),
          this.loadOrders(),
          this.loadReports(),
        ]);
      });
    },

    async setView(view) {
      this.view = view;
      this.audit = null;
      await this.refreshCurrent();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    },

    async refreshCurrent() {
      try {
        if (this.view === 'dashboard') await this.loadInitialData();
        if (this.view === 'mozo') await Promise.all([this.loadProducts(), this.loadCategories(), this.loadTables()]);
        if (this.view === 'pedidos') await this.loadOrders();
        if (this.view === 'inventario') await this.loadInventoryModule();
        if (this.view === 'pagos') await this.loadPayments();
        if (this.view === 'reportes') await this.loadReports();
        if (this.view === 'facturacion') await this.loadSunatModule();
        if (this.view === 'integraciones') await this.loadFutureWork();
        if (this.view === 'crud') await this.loadCrudTable();
        if (this.view === 'logs') await this.loadLogs();
      } catch (error) {
        this.notify(error.message, 'error');
      }
    },

    async loadProducts() {
      const [all, available] = await Promise.all([
        this.api('/productos?limit=200'),
        this.api('/productos/disponibles?limit=200'),
      ]);
      this.products = all.data || [];
      this.availableProducts = available.data || [];
    },

    async loadCategories() {
      const data = await this.api('/categorias?limit=100');
      this.categories = data.data || [];
    },

    async loadTables() {
      const data = await this.api('/mesas?limit=100');
      this.mesas = data.data || [];
    },

    searchProductsDebounced() {
      window.clearTimeout(this.searchTimer);
      this.searchTimer = window.setTimeout(this.searchProducts, 320);
    },

    async searchProducts() {
      const q = this.productSearch.trim();
      try {
        if (!q) {
          const data = await this.api('/productos/disponibles?limit=200');
          this.availableProducts = data.data || [];
          return;
        }
        const data = await this.api(`/productos/buscar?q=${encodeURIComponent(q)}&limit=200`);
        this.availableProducts = data.data || [];
      } catch (error) {
        this.notify(error.message, 'error');
      }
    },

    addToCart(product) {
      const stock = Number(product.stock_actual ?? 0);
      const found = this.cart.find(i => Number(i.id_producto) === Number(product.id_producto));
      const currentQty = found ? Number(found.cantidad) : 0;
      if (currentQty >= stock) {
        this.notify(`Stock insuficiente para ${product.nombre}. Disponible: ${stock}.`, 'error');
        return;
      }
      if (found) {
        found.cantidad += 1;
      } else {
        this.cart.push({
          id_producto: product.id_producto,
          nombre: product.nombre,
          precio: Number(product.precio || 0),
          cantidad: 1,
          stock_actual: stock,
        });
      }
    },

    changeQty(id_producto, delta) {
      const item = this.cart.find(i => Number(i.id_producto) === Number(id_producto));
      if (!item) return;
      const next = Number(item.cantidad) + Number(delta);
      if (next <= 0) {
        this.removeFromCart(id_producto);
        return;
      }
      if (next > Number(item.stock_actual)) {
        this.notify(`Máximo disponible: ${item.stock_actual}.`, 'error');
        return;
      }
      item.cantidad = next;
    },

    removeFromCart(id_producto) {
      this.cart = this.cart.filter(i => Number(i.id_producto) !== Number(id_producto));
    },

    clearCart() {
      this.cart = [];
      this.orderForm.comentario = '';
      this.orderForm.id_mesa = null;
    },

    async createOrder() {
      if (!this.cart.length) {
        this.notify('Agrega productos al carrito antes de registrar el pedido.', 'error');
        return;
      }
      await this.withLoading(async () => {
        const payload = {
          id_usuario: 1,
          id_mesa: this.orderForm.id_mesa || null,
          comentario: this.orderForm.comentario,
          items: this.cart.map(i => ({ id_producto: i.id_producto, cantidad: i.cantidad })),
        };
        const result = await this.api('/funcionalidad/pedidos', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
        this.notify(`Pedido #${result.pedido.id_pedido} registrado correctamente.`);
        this.clearCart();
        await Promise.all([this.loadProducts(), this.loadTables(), this.loadOrders(), this.loadReports()]);
      });
    },

    async loadOrders() {
      const data = await this.api('/pedidos?limit=200');
      this.orders = (data.data || []).map(o => ({ ...o, _nextEstado: o.estado }));
    },

    async updateOrderStatus(order) {
      await this.withLoading(async () => {
        const updated = await this.api(`/funcionalidad/pedidos/${order.id_pedido}/estado`, {
          method: 'PATCH',
          body: JSON.stringify({ estado: order._nextEstado }),
        });
        this.notify(`Pedido #${updated.id_pedido} actualizado a ${updated.estado}.`);
        await Promise.all([this.loadOrders(), this.loadTables(), this.loadReports()]);
      });
    },

    async loadAudit(id_pedido) {
      await this.withLoading(async () => {
        this.audit = await this.api(`/funcionalidad/pedidos/${id_pedido}/auditoria`);
      });
    },

    async loadInventoryModule() {
      await Promise.all([
        this.loadProducts(),
        this.loadInventory(),
        this.loadInventoryMovements(),
      ]);
    },

    async loadInventory() {
      const data = await this.api('/inventario?limit=200');
      this.inventory = data.data || [];
    },

    async loadInventoryMovements() {
      const data = await this.api('/inventario_movimientos?limit=100');
      this.inventoryMovements = data.data || [];
    },

    async adjustInventory() {
      if (!this.inventoryForm.id_producto || !this.inventoryForm.cantidad) {
        this.notify('Selecciona un producto e ingresa una cantidad válida.', 'error');
        return;
      }
      await this.withLoading(async () => {
        const result = await this.api('/funcionalidad/inventario/ajuste', {
          method: 'POST',
          body: JSON.stringify(this.inventoryForm),
        });
        this.notify(`Inventario actualizado. Nuevo stock: ${result.stock_nuevo}.`);
        await this.loadInventoryModule();
      });
    },

    async loadPayments() {
      const data = await this.api('/transacciones?limit=100');
      this.transactions = data.data || [];
      if (!this.orders.length) await this.loadOrders();
    },

    async confirmPayment() {
      if (!this.paymentForm.id_pedido) {
        this.notify('Ingresa el ID del pedido que será pagado.', 'error');
        return;
      }
      await this.withLoading(async () => {
        const result = await this.api(`/funcionalidad/pedidos/${this.paymentForm.id_pedido}/pago`, {
          method: 'POST',
          body: JSON.stringify({
            metodo_pago: this.paymentForm.metodo_pago,
            referencia: this.paymentForm.referencia,
          }),
        });
        this.notify(`Pago confirmado por ${this.money(result.monto)}.`);
        this.paymentForm.id_pedido = null;
        this.paymentForm.referencia = '';
        await Promise.all([this.loadPayments(), this.loadOrders(), this.loadReports()]);
      });
    },

    async loadReports() {
      const params = new URLSearchParams();
      if (this.reportFilters.desde) params.set('desde', this.reportFilters.desde);
      if (this.reportFilters.hasta) params.set('hasta', this.reportFilters.hasta);
      const qs = params.toString() ? `?${params.toString()}` : '';
      const [ventas, top, stockBajo, estados, fondo] = await Promise.all([
        this.api(`/reportes/ventas${qs}`),
        this.api('/reportes/productos-mas-vendidos?limit=10'),
        this.api('/reportes/stock-bajo'),
        this.api('/reportes/pedidos-por-estado'),
        this.api('/reportes/fondo-social'),
      ]);
      this.reports = {
        ventas,
        topProducts: top || [],
        stockBajo: stockBajo || [],
        ordersByStatus: estados || [],
        fondoSocial: fondo || {},
      };
    },

    async loadFutureWork() {
      const data = await this.api('/trabajos-futuros');
      this.futureWork = data.trabajos_futuros || [];
    },

    async simulateFuture(item) {
      await this.withLoading(async () => {
        let payload = {
          origen_frontend: 'Vue.js',
          fecha_demo: new Date().toISOString(),
          observacion: `Simulación de ${item.nombre}`,
        };
        if (String(item.endpoint).includes('/sunat/comprobantes')) {
          payload = this.parseJsonEditor(this.sunatForm.manualJson);
        }
        this.integrationResult = await this.api(item.endpoint.replace('/api', ''), {
          method: 'POST',
          body: JSON.stringify(payload),
        });
        this.notify(`${item.nombre} ejecutado correctamente.`);
        if (String(item.endpoint).includes('/sunat/comprobantes')) await this.loadSunatModule();
      });
    },

    async consultRuc() {
      if (!this.sunatForm.ruc) {
        this.notify('Ingresa un RUC para consultar.', 'error');
        return;
      }
      await this.withLoading(async () => {
        this.integrationResult = await this.api(`/sunat/ruc/${encodeURIComponent(this.sunatForm.ruc)}`);
        this.notify('Consulta SUNAT simulada correctamente.');
      });
    },

    async loadSunatModule() {
      const [config, docs] = await Promise.all([
        this.api('/sunat/config'),
        this.api('/sunat/comprobantes?limit=100'),
      ]);
      this.sunatConfig = config;
      this.comprobantes = docs.data || [];
      if (!this.orders.length) await this.loadOrders();
    },

    paidOrdersForSunat() {
      return this.orders.filter(o => o.estado === 'pagado' || Number(o.total) > 0);
    },

    async emitSunatFromPedido() {
      if (!this.sunatForm.id_pedido) {
        this.notify('Selecciona o ingresa el ID del pedido a facturar.', 'error');
        return;
      }
      await this.withLoading(async () => {
        const endpoint = `/sunat/pedidos/${this.sunatForm.id_pedido}/${this.sunatForm.tipo_comprobante}`;
        const payload = {
          cliente: { ...this.sunatForm.cliente },
          observacion: 'Comprobante emitido desde el frontend Vue.js',
        };
        this.integrationResult = await this.api(endpoint, {
          method: 'POST',
          body: JSON.stringify(payload),
        });
        this.notify(`${this.sunatForm.tipo_comprobante} emitida y registrada.`);
        await this.loadSunatModule();
      });
    },

    async emitSunatManual() {
      await this.withLoading(async () => {
        const payload = this.parseJsonEditor(this.sunatForm.manualJson);
        this.integrationResult = await this.api('/sunat/comprobantes', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
        this.notify('Comprobante manual emitido y registrado.');
        await this.loadSunatModule();
      });
    },

    async consultSunatDoc(doc) {
      await this.withLoading(async () => {
        this.integrationResult = await this.api(`/sunat/comprobantes/${doc.id_comprobante}/consultar`, {
          method: 'POST',
          body: JSON.stringify({}),
        });
        this.notify(`Estado consultado para ${doc.serie}-${doc.numero}.`);
        await this.loadSunatModule();
      });
    },

    async cancelSunatDoc(doc) {
      if (!window.confirm(`¿Anular ${doc.serie}-${doc.numero}?`)) return;
      await this.withLoading(async () => {
        this.integrationResult = await this.api(`/sunat/comprobantes/${doc.id_comprobante}/anular`, {
          method: 'POST',
          body: JSON.stringify({ motivo: 'Anulación solicitada desde frontend Vue.js' }),
        });
        this.notify(`Comprobante ${doc.serie}-${doc.numero} anulado.`);
        await this.loadSunatModule();
      });
    },


    async createPedidosYa() {
      await this.withLoading(async () => {
        this.integrationResult = await this.api('/pedidosya/nuevo', { method: 'POST', body: JSON.stringify({}) });
        this.notify('Pedido PedidosYa simulado correctamente.');
      });
    },

    async loadCrudTable() {
      this.crud.createJson = this.crudExamples[this.crud.table] || '{\n\n}';
      const data = await this.api(`/${this.crud.table}?limit=100`);
      this.crud.rows = data.data || [];
    },

    crudRowKey(row) {
      const pk = this.crudPk[this.crud.table];
      return row[pk] || JSON.stringify(row);
    },

    parseJsonEditor(text) {
      try {
        return JSON.parse(text || '{}');
      } catch (error) {
        throw new Error('El JSON ingresado no es válido. Revisa comas, llaves y comillas.');
      }
    },

    async createCrudRecord() {
      await this.withLoading(async () => {
        const payload = this.parseJsonEditor(this.crud.createJson);
        await this.api(`/${this.crud.table}`, {
          method: 'POST',
          body: JSON.stringify(payload),
        });
        this.notify(`Registro creado en ${this.crud.table}.`);
        await this.loadCrudTable();
      });
    },

    async updateCrudRecord() {
      if (!this.crud.updateId) {
        this.notify('Ingresa el ID del registro que deseas actualizar.', 'error');
        return;
      }
      await this.withLoading(async () => {
        const payload = this.parseJsonEditor(this.crud.updateJson);
        await this.api(`/${this.crud.table}/${this.crud.updateId}`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        });
        this.notify(`Registro ${this.crud.updateId} actualizado.`);
        await this.loadCrudTable();
      });
    },

    async deleteCrudRecord(row) {
      const pk = this.crudPk[this.crud.table];
      const id = row[pk];
      if (!id) return;
      if (!window.confirm(`¿Eliminar registro ${id} de ${this.crud.table}?`)) return;
      await this.withLoading(async () => {
        await this.api(`/${this.crud.table}/${id}`, { method: 'DELETE' });
        this.notify(`Registro ${id} eliminado.`);
        await this.loadCrudTable();
      });
    },

    async loadLogs() {
      const data = await this.api('/logs?limit=100');
      this.logs = data.data || [];
    },

    restoreTokenFromHash() {
      const hash = window.location.hash.replace(/^#/, '');
      if (!hash) return;
      const params = new URLSearchParams(hash);
      const token = params.get('access_token');
      if (token) {
        localStorage.setItem('api_token', token);
        history.replaceState(null, '', window.location.pathname);
        this.notify('Sesión OAuth restaurada desde Keycloak.');
      }
    },

    async demoLogin() {
      await this.withLoading(async () => {
        const data = await this.api('/auth/demo-login', { method: 'POST', body: JSON.stringify({}) });
        localStorage.setItem('api_token', data.access_token);
        this.currentUser = data.user;
        this.view = 'dashboard';
        await this.loadInitialData();
        this.notify('Acceso autorizado con token demo.');
      });
    },

    async keycloakLogin() {
      try {
        const config = this.authConfig || await this.api('/auth/config');
        this.authConfig = config;
        if (!config.oauth_keycloak_configurado) {
          this.notify('Keycloak OAuth no está configurado. Usa Token demo para exposición offline.', 'error');
          return;
        }
        window.location.href = '/api/auth/oauth/keycloak/login?next=/';
      } catch (error) {
        this.notify(error.message, 'error');
      }
    },

    async getMe(showError = true) {
      const token = localStorage.getItem('api_token');
      if (!token) {
        this.currentUser = null;
        return false;
      }
      try {
        const data = await this.api('/auth/me');
        this.currentUser = data.user;
        return true;
      } catch (error) {
        localStorage.removeItem('api_token');
        this.currentUser = null;
        if (showError) this.notify(error.message, 'error');
        return false;
      }
    },

    async logout() {
      // Primero se llama al backend con el Bearer token activo para cerrar la sesión
      // local y revocar el access token de Keycloak cuando corresponde.
      let backendMessage = 'Sesión cerrada.';
      try {
        const data = await this.api('/auth/logout', { method: 'POST', body: JSON.stringify({}) });
        backendMessage = data.keycloak_revoked
          ? 'Sesión cerrada y autorización Keycloak revocada.'
          : 'Sesión cerrada localmente.';
      } catch (_) {
        backendMessage = 'Sesión cerrada localmente.';
      } finally {
        localStorage.removeItem('api_token');
        this.currentUser = null;
        this.cart = [];
        this.view = 'dashboard';
      }
      this.notify(`${backendMessage} Vuelve a autenticarte para ingresar al panel.`);
    },
  },
}
</script>
