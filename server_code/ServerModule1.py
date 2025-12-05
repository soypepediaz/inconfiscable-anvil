# ============================================
# CÓDIGO BACKEND PARA ANVIL.WORKS
# Inconfiscable - Calculadora DCA
# ============================================
# 
# INSTRUCCIONES:
# 1. En Anvil, ve a Server Code (lado izquierdo)
# 2. Copia TODO este código en el archivo "ServerModule1"
# 3. Guarda (Ctrl+S)
# 4. Ya está listo para usar desde el frontend
#
# ============================================

import anvil.server
import yfinance as yf
from datetime import datetime, timedelta
from typing import Tuple, List, Dict

# Configurar Anvil para aceptar llamadas desde el cliente
anvil.server.enable_cors("*")

# ============================================
# FUNCIONES DE UTILIDAD
# ============================================

@anvil.server.callable
def get_bitcoin_prices(start_date_str: str, end_date_str: str) -> Dict:
    """
    Obtiene histórico de precios de Bitcoin usando yfinance.
    
    Args:
        start_date_str: Fecha inicio en formato 'YYYY-MM-DD'
        end_date_str: Fecha fin en formato 'YYYY-MM-DD'
    
    Returns:
        Diccionario {fecha_str: precio_float} o error
    """
    try:
        # Convertir strings a datetime
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        # Descargar datos de Bitcoin usando yfinance
        btc_data = yf.download('BTC-USD', start=start_date, end=end_date, progress=False)
        
        if btc_data.empty:
            return {
                'success': False,
                'error': 'No se encontraron datos de Bitcoin para el período seleccionado.'
            }
        
        # Convertir a diccionario {fecha_str: precio_cierre}
        prices = {}
        
        try:
            # Método 1: Acceso directo a columna 'Close' (formato simple)
            if 'Close' in btc_data.columns:
                for index, row in btc_data.iterrows():
                    try:
                        date_str = index.date().isoformat()
                        close_price = float(row['Close'])
                        if close_price > 0:
                            prices[date_str] = close_price
                    except (ValueError, TypeError):
                        continue
            else:
                # Método 2: MultiIndex (formato reciente de yfinance)
                for index in btc_data.index:
                    try:
                        date_str = index.date().isoformat()
                        close_value = None
                        
                        # Busca la columna Close en MultiIndex
                        if isinstance(btc_data.columns, pd.MultiIndex):
                            for col in btc_data.columns:
                                if isinstance(col, tuple) and 'Close' in col:
                                    try:
                                        val = btc_data.loc[index, col]
                                        if pd.notna(val):
                                            close_value = float(val)
                                            break
                                    except:
                                        continue
                        
                        # Si no encontró, busca en columnas simples
                        if close_value is None:
                            for col in btc_data.columns:
                                if 'Close' in str(col):
                                    try:
                                        val = btc_data.loc[index, col]
                                        if pd.notna(val):
                                            close_value = float(val)
                                            break
                                    except:
                                        continue
                        
                        # Guardar si es válido
                        if close_value is not None and close_value > 0:
                            prices[date_str] = close_value
                    except Exception:
                        continue
        
        except Exception as e:
            return {
                'success': False,
                'error': f'Error al procesar datos: {str(e)}'
            }
        
        if not prices:
            return {
                'success': False,
                'error': 'No se pudieron extraer precios válidos.'
            }
        
        return {
            'success': True,
            'prices': prices,
            'count': len(prices)
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'Error: {str(e)}'
        }


@anvil.server.callable
def get_purchase_dates(start_date_str: str, end_date_str: str, frequency: str, 
                       day_of_week: int = None, day_of_month: int = None) -> List[str]:
    """
    Genera lista de fechas de compra según la frecuencia especificada.
    
    Args:
        start_date_str: Fecha inicio en formato 'YYYY-MM-DD'
        end_date_str: Fecha fin en formato 'YYYY-MM-DD'
        frequency: 'Diaria', 'Semanal' o 'Mensual'
        day_of_week: 0-6 (0=Lunes) para frecuencia semanal
        day_of_month: 1-31 para frecuencia mensual
    
    Returns:
        Lista de fechas en formato 'YYYY-MM-DD'
    """
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        dates = []
        current_date = start_date
        
        if frequency == "Diaria":
            while current_date <= end_date:
                dates.append(current_date.date().isoformat())
                current_date += timedelta(days=1)
        
        elif frequency == "Semanal":
            while current_date <= end_date:
                if current_date.weekday() == day_of_week:
                    dates.append(current_date.date().isoformat())
                current_date += timedelta(days=1)
        
        elif frequency == "Mensual":
            month_date = start_date
            while month_date <= end_date:
                # Manejo de meses con menos días
                if day_of_month == 31:
                    next_month = (month_date.replace(day=1) + timedelta(days=32)).replace(day=1)
                    last_day = (next_month - timedelta(days=1)).day
                    target_day = min(day_of_month, last_day)
                else:
                    target_day = day_of_month
                
                try:
                    purchase_date = month_date.replace(day=target_day)
                    if start_date <= purchase_date <= end_date:
                        dates.append(purchase_date.date().isoformat())
                    # Avanzar al siguiente mes
                    if month_date.month == 12:
                        month_date = month_date.replace(year=month_date.year + 1, month=1)
                    else:
                        month_date = month_date.replace(month=month_date.month + 1)
                except ValueError:
                    if month_date.month == 12:
                        month_date = month_date.replace(year=month_date.year + 1, month=1)
                    else:
                        month_date = month_date.replace(month=month_date.month + 1)
        
        return sorted(list(set(dates)))
        
    except Exception as e:
        return {'error': str(e)}


@anvil.server.callable
def calculate_dca(start_date_str: str, end_date_str: str, amount_usd: float, 
                  frequency: str, day_of_week: int = None, day_of_month: int = None,
                  bitcoin_prices: Dict = None) -> Dict:
    """
    Calcula DCA y retorna resultados con lista de compras.
    
    Args:
        start_date_str: Fecha inicio en formato 'YYYY-MM-DD'
        end_date_str: Fecha fin en formato 'YYYY-MM-DD'
        amount_usd: Cantidad a invertir por período
        frequency: 'Diaria', 'Semanal' o 'Mensual'
        day_of_week: 0-6 para semanal
        day_of_month: 1-31 para mensual
        bitcoin_prices: Diccionario de precios {fecha_str: precio}
    
    Returns:
        Diccionario con resultados del DCA
    """
    try:
        if not bitcoin_prices:
            return {
                'success': False,
                'error': 'No hay precios disponibles'
            }
        
        purchase_dates = get_purchase_dates(start_date_str, end_date_str, frequency, 
                                           day_of_week, day_of_month)
        
        if isinstance(purchase_dates, dict) and 'error' in purchase_dates:
            return {
                'success': False,
                'error': purchase_dates['error']
            }
        
        if not purchase_dates:
            return {
                'success': False,
                'error': 'No se generaron fechas de compra'
            }
        
        total_btc = 0
        total_invested = 0
        purchases = []
        
        # Obtener fechas disponibles en orden
        bitcoin_dates = sorted(bitcoin_prices.keys())
        
        for target_date in purchase_dates:
            # Buscar precio en la fecha exacta o más cercana anterior
            price = None
            
            if target_date in bitcoin_prices:
                price = bitcoin_prices[target_date]
            else:
                # Buscar el precio más cercano anterior
                for btc_date in reversed(bitcoin_dates):
                    if btc_date <= target_date:
                        price = bitcoin_prices[btc_date]
                        break
            
            # Si no hay precio anterior, usar el primero disponible
            if price is None and bitcoin_dates:
                price = bitcoin_prices[bitcoin_dates[0]]
            
            # Si encontramos un precio, registrar la compra
            if price is not None and price > 0:
                btc_bought = amount_usd / price
                total_btc += btc_bought
                total_invested += amount_usd
                purchases.append({
                    'date': target_date,
                    'price': round(price, 2),
                    'amount_usd': round(amount_usd, 2),
                    'btc_bought': round(btc_bought, 8)
                })
        
        if total_btc <= 0:
            return {
                'success': False,
                'error': 'No se realizaron compras'
            }
        
        return {
            'success': True,
            'btc_accumulated': round(total_btc, 8),
            'total_invested': round(total_invested, 2),
            'purchases_count': len(purchases),
            'purchases': purchases
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'Error en cálculo: {str(e)}'
        }


@anvil.server.callable
def calculate_scenarios(btc_accumulated: float, total_invested: float, 
                       future_price: float, start_date_str: str, end_date_str: str) -> Dict:
    """
    Calcula ambos escenarios (La Trampa vs Lo Inconfiscable).
    
    Args:
        btc_accumulated: BTC acumulado
        total_invested: Total invertido en USD
        future_price: Precio futuro esperado
        start_date_str: Fecha inicio
        end_date_str: Fecha fin
    
    Returns:
        Diccionario con cálculos de ambos escenarios
    """
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        years = (end_date - start_date).days / 365.25
        
        # Escenario A: La Trampa (con impuestos)
        gross_value_a = btc_accumulated * future_price
        taxes = gross_value_a * 0.25  # 25% de impuestos
        net_value_a = gross_value_a - taxes
        roi_a = ((net_value_a - total_invested) / total_invested * 100) if total_invested > 0 else 0
        
        # CAGR para Escenario A
        if total_invested > 0 and years > 0:
            cagr_a = (pow(net_value_a / total_invested, 1 / years) - 1) * 100
        else:
            cagr_a = 0
        
        # Escenario B: Lo Inconfiscable (sin impuestos)
        gross_value_b = btc_accumulated * future_price
        net_value_b = gross_value_b
        roi_b = ((net_value_b - total_invested) / total_invested * 100) if total_invested > 0 else 0
        
        # CAGR para Escenario B
        if total_invested > 0 and years > 0:
            cagr_b = (pow(net_value_b / total_invested, 1 / years) - 1) * 100
        else:
            cagr_b = 0
        
        difference = net_value_b - net_value_a
        
        return {
            'success': True,
            'scenario_a': {
                'name': 'La Trampa',
                'gross_value': round(gross_value_a, 2),
                'taxes': round(taxes, 2),
                'net_value': round(net_value_a, 2),
                'roi': round(roi_a, 2),
                'cagr': round(cagr_a, 2)
            },
            'scenario_b': {
                'name': 'Lo Inconfiscable',
                'gross_value': round(gross_value_b, 2),
                'taxes': 0,
                'net_value': round(net_value_b, 2),
                'roi': round(roi_b, 2),
                'cagr': round(cagr_b, 2)
            },
            'difference': round(difference, 2),
            'years': round(years, 2)
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'Error: {str(e)}'
        }


@anvil.server.callable
def full_simulation(start_date_str: str, end_date_str: str, amount_usd: float,
                   frequency: str, future_price: float, future_date_str: str,
                   day_of_week: int = None, day_of_month: int = None) -> Dict:
    """
    Ejecuta la simulación completa en un solo llamado.
    
    Returns:
        Diccionario con todos los resultados
    """
    try:
        # Paso 1: Obtener precios históricos
        prices_result = get_bitcoin_prices(start_date_str, end_date_str)
        if not prices_result.get('success'):
            return {'success': False, 'error': prices_result.get('error', 'Error desconocido')}
        
        bitcoin_prices = prices_result['prices']
        
        # Paso 2: Calcular DCA
        dca_result = calculate_dca(start_date_str, end_date_str, amount_usd, frequency,
                                   day_of_week, day_of_month, bitcoin_prices)
        if not dca_result.get('success'):
            return {'success': False, 'error': dca_result.get('error', 'Error en DCA')}
        
        btc_accumulated = dca_result['btc_accumulated']
        total_invested = dca_result['total_invested']
        purchases = dca_result['purchases']
        
        # Paso 3: Calcular escenarios
        scenarios_result = calculate_scenarios(btc_accumulated, total_invested, 
                                              future_price, start_date_str, future_date_str)
        if not scenarios_result.get('success'):
            return {'success': False, 'error': scenarios_result.get('error', 'Error en escenarios')}
        
        return {
            'success': True,
            'btc_accumulated': btc_accumulated,
            'total_invested': total_invested,
            'purchases_count': dca_result['purchases_count'],
            'purchases': purchases,
            'scenario_a': scenarios_result['scenario_a'],
            'scenario_b': scenarios_result['scenario_b'],
            'difference': scenarios_result['difference'],
            'years': scenarios_result['years']
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'Error en simulación: {str(e)}'
        }
