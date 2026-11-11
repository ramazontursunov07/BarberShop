from django.db import transaction

from .models import Product, ProductReservation

MAX_QUANTITY = 20


class ProductError(ValueError):
    pass


def reserve(user, product_id: int, quantity: int) -> ProductReservation:
    if not 1 <= quantity <= MAX_QUANTITY:
        raise ProductError(f"Miqdor 1 dan {MAX_QUANTITY} gacha bo'lishi kerak")
    with transaction.atomic():
        product = (
            Product.objects.select_for_update()
            .filter(pk=product_id, is_active=True, shop__is_active=True, shop__is_approved=True)
            .first()
        )
        if product is None:
            raise ProductError("Mahsulot topilmadi")
        if product.stock < quantity:
            raise ProductError(f"Omborda faqat {product.stock} ta qolgan")
        product.stock -= quantity
        product.save(update_fields=["stock"])
        return ProductReservation.objects.create(
            client=user, product=product, quantity=quantity, unit_price=product.price
        )


def cancel_by_client(user, reservation_id: int) -> ProductReservation:
    with transaction.atomic():
        res = (
            ProductReservation.objects.select_for_update()
            .filter(pk=reservation_id, client=user).select_related("product").first()
        )
        if res is None:
            raise ProductError("Band qilish topilmadi")
        return _release(res)


def set_status_by_owner(owner, reservation_id: int, new_status: str) -> ProductReservation:
    """Egasi: reserved -> picked_up yoki cancelled (ombor qaytadi)."""
    if new_status not in (ProductReservation.Status.PICKED_UP, ProductReservation.Status.CANCELLED):
        raise ProductError("Status faqat picked_up yoki cancelled bo'lishi mumkin")
    with transaction.atomic():
        res = (
            ProductReservation.objects.select_for_update()
            .filter(pk=reservation_id, product__shop__owner=owner).select_related("product").first()
        )
        if res is None:
            raise ProductError("Band qilish topilmadi")
        if new_status == ProductReservation.Status.CANCELLED:
            return _release(res)
        if res.status != ProductReservation.Status.RESERVED:
            raise ProductError(f"Holati '{res.status}', o'zgartirib bo'lmaydi")
        res.status = new_status
        res.save(update_fields=["status"])
        return res


def _release(res: ProductReservation) -> ProductReservation:
    if res.status != ProductReservation.Status.RESERVED:
        raise ProductError(f"Holati '{res.status}', bekor qilib bo'lmaydi")
    product = Product.objects.select_for_update().get(pk=res.product_id)
    product.stock += res.quantity
    product.save(update_fields=["stock"])
    res.status = ProductReservation.Status.CANCELLED
    res.save(update_fields=["status"])
    return res
